"""HMM note segmenter: turns a pitch track into notes (task 1.3; SPEC § 4.3).

Plain-language version: imagine a singer who, at every 10 ms moment, is either silent,
starting a note ("attack"), or holding a note ("sustain"), on one of the semitones from
C2 to C6. A hidden Markov model (HMM) scores every possible story of states against what
we measured (the pitch track, whether anyone is singing, and how strongly a new sound
starts), and the Viterbi algorithm picks the most likely story. Runs of attack+sustain on
one pitch become notes.

Why this beats splitting the pitch curve by hand:
- vibrato and wobble stay inside one sustain state (it tolerates ±1 semitone wiggle);
- a short pitch blip can't start a new note unless it lasts (staying is far likelier
  than switching);
- a re-sung note on the same pitch is found from the onset (attack) evidence;
- breaths and consonants don't become notes, because a note needs an attack and enough
  frames of sustain to be worth it.

After Mauch et al. 2015 ("Computer-aided melody note transcription using the Tony
software"), simplified: one pitch per semitone and observation models built directly from
the tracker's output instead of pYIN's pitch candidates.
"""

from __future__ import annotations

from dataclasses import dataclass

import librosa
import numpy as np

from clay_research.datasets.common import Note, PitchTrack


@dataclass(frozen=True)
class SegmenterParams:
    """Every knob of the model, in plain units. Tuned with cross-validation (see tune.py)."""

    midi_low: int = 36  # C2
    midi_high: int = 84  # C6
    sustain_sigma: float = 0.55  # semitones of wiggle tolerated while holding a note
    attack_sigma: float = 1.5  # pitch is less settled during an attack
    unvoiced_in_note: float = 0.08  # P(tracker says unvoiced | someone is holding a note)
    voiced_in_silence: float = 0.05  # P(tracker says voiced | silence): ghost pitch
    p_stay_sustain: float = 0.985  # per 10 ms; sets how long notes tend to be
    p_stay_attack: float = 0.6  # attacks last a few frames
    p_note_change: float = 0.004  # sustain -> attack of a *different* pitch
    p_reattack: float = 0.0015  # sustain -> attack of the same pitch (needs onset evidence)
    p_start: float = 0.02  # silence -> attack
    onset_weight: float = 3.0  # how much onset strength favours attacks
    onset_mix: float = 0.0  # 0 = spectral flux only, 1 = loudness rise only
    motion_weight: float = 0.0  # how much a moving pitch favours attacks
    min_note_s: float = 0.06  # shorter notes are dropped
    trim_fraction: float = 0.2  # note pitch ignores this much at each end (scoops, falls)


def _normalize(x: np.ndarray) -> np.ndarray:
    scale = np.percentile(x, 99) if np.any(x > 0) else 1.0
    return np.clip(x / max(scale, 1e-9), 0.0, 1.0)


def _onset_strength(audio: np.ndarray, sample_rate: int, times: np.ndarray) -> np.ndarray:
    """Spectral-flux onset strength (how much the spectrum changes), on the pitch frames, 0..1."""
    hop = 160 if sample_rate <= 16000 else 512
    env = librosa.onset.onset_strength(y=audio, sr=sample_rate, hop_length=hop)
    env_times = librosa.times_like(env, sr=sample_rate, hop_length=hop)
    return _normalize(np.interp(times, env_times, env))


def _loudness_rise(audio: np.ndarray, sample_rate: int, times: np.ndarray) -> np.ndarray:
    """How much louder the voice got over the last ~60 ms, in dB, on the pitch frames, 0..1.

    Sung notes usually start with a loudness rise (after a consonant or breath dip), even
    when the pitch barely moves; this catches re-attacks spectral flux can miss."""
    hop = max(1, int(round(0.005 * sample_rate)))  # 5 ms
    rms = librosa.feature.rms(y=audio, frame_length=4 * hop, hop_length=hop)[0]
    db = 20 * np.log10(np.maximum(rms, 1e-5))
    look = 12  # 60 ms
    padded = np.concatenate([np.full(look, db[0]), db])
    recent_min = np.lib.stride_tricks.sliding_window_view(padded, look + 1)[:, :-1].min(axis=1)
    rise = np.maximum(db - recent_min[: len(db)], 0.0)
    rise_times = np.arange(len(rise)) * hop / sample_rate
    return _normalize(np.interp(times, rise_times, rise))


def _pitch_motion(midi: np.ndarray, hop_s: float) -> np.ndarray:
    """How fast the pitch is moving (semitones per 30 ms, voiced frames only), 0..1."""
    m = np.where(np.isfinite(midi), midi, np.nan)
    step = max(1, int(round(0.03 / hop_s)))
    motion = np.zeros(len(m))
    if len(m) > step:
        d = np.abs(m[step:] - m[:-step])
        motion[step // 2 : step // 2 + len(d)] = np.nan_to_num(d, nan=0.0)
    return np.clip(motion / 1.0, 0.0, 1.0)


def _log_observations(
    midi: np.ndarray,
    voiced: np.ndarray,
    onset: np.ndarray,
    motion: np.ndarray,
    pitches: np.ndarray,
    p: SegmenterParams,
) -> np.ndarray:
    """log P(observation | state) for states [silence, attack(pitches), sustain(pitches)]."""
    n_frames, n_pitch = len(midi), len(pitches)
    out = np.empty((1 + 2 * n_pitch, n_frames))

    # Silence: expects no pitch and no onset.
    out[0] = np.where(voiced, np.log(p.voiced_in_silence), np.log(1 - p.voiced_in_silence))
    out[0] += np.log1p(-0.5 * onset)

    diff = np.where(voiced, midi, 0.0)[None, :] - pitches[:, None]

    def pitched(sigma: float) -> np.ndarray:
        # Gaussian in semitones, normalized so a perfect match scores 0 (log 1); a floor
        # keeps wild octave jumps from making a state impossible.
        g = np.maximum(np.exp(-0.5 * (diff / sigma) ** 2), 1e-4)
        return np.where(
            voiced[None, :], np.log(g) + np.log(1 - p.unvoiced_in_note), np.log(p.unvoiced_in_note)
        )

    out[1 : 1 + n_pitch] = (
        pitched(p.attack_sigma)
        + p.onset_weight * np.log(0.05 + onset)[None, :]
        + p.motion_weight * np.log(0.05 + motion)[None, :]
    )
    out[1 + n_pitch :] = pitched(p.sustain_sigma) + p.onset_weight * np.log(1.05 - onset)[None, :]
    return out


def _transitions(n_pitch: int, p: SegmenterParams) -> np.ndarray:
    """Row-stochastic transition matrix over [silence, attack(n), sustain(n)]."""
    n = 1 + 2 * n_pitch
    a = slice(1, 1 + n_pitch)
    s = slice(1 + n_pitch, n)
    t = np.zeros((n, n))
    t[0, 0] = 1 - p.p_start
    t[0, a] = p.p_start / n_pitch
    eye = np.eye(n_pitch)
    t[a, a] = eye * p.p_stay_attack
    t[a, s] = eye * (1 - p.p_stay_attack)
    p_end = max(1 - p.p_stay_sustain - p.p_note_change - p.p_reattack, 1e-6)
    t[s, s] = eye * p.p_stay_sustain
    t[s, 0] = p_end
    off = 1 - eye
    t[s, a] = eye * p.p_reattack + off * (p.p_note_change / (n_pitch - 1))
    return t / t.sum(axis=1, keepdims=True)


def _note_pitch(midi: np.ndarray, weight: np.ndarray, trim: float) -> float | None:
    """Amplitude-weighted median of the note's stable middle (SPEC decision 4)."""
    ok = np.isfinite(midi)
    if not ok.any():
        return None
    idx = np.nonzero(ok)[0]
    cut = int(len(idx) * trim)
    if len(idx) - 2 * cut >= 3:
        idx = idx[cut : len(idx) - cut]
    values, w = midi[idx], np.maximum(weight[idx], 1e-9)
    order = np.argsort(values)
    cum = np.cumsum(w[order])
    return float(values[order][np.searchsorted(cum, cum[-1] / 2)])


@dataclass(frozen=True)
class Features:
    """Everything the decoder needs, computed once per clip (pitch, voicing, onset, level)."""

    times: np.ndarray
    hop_s: float
    midi: np.ndarray  # NaN where unvoiced
    voiced: np.ndarray
    onset: np.ndarray  # spectral flux, 0..1
    rise: np.ndarray  # loudness rise, 0..1
    motion: np.ndarray  # pitch motion, 0..1
    loud: np.ndarray  # RMS, for weighting the note pitch


def features(
    track: PitchTrack, audio: np.ndarray | None = None, sample_rate: int | None = None
) -> Features | None:
    times = np.asarray(track.times, dtype=float)
    if len(times) < 2:
        return None
    hop_s = float(np.median(np.diff(times)))
    hz = np.asarray(track.frequencies_hz, dtype=float)
    voiced = hz > 0
    with np.errstate(divide="ignore"):
        midi = np.where(voiced, 69 + 12 * np.log2(np.where(voiced, hz, 1.0) / 440.0), np.nan)
    if audio is not None and sample_rate:
        onset = _onset_strength(audio, sample_rate, times)
        rise = _loudness_rise(audio, sample_rate, times)
        frame = max(1, int(round(hop_s * sample_rate)))
        rms = librosa.feature.rms(y=audio, frame_length=2 * frame, hop_length=frame)[0]
        loud = np.interp(times, np.arange(len(rms)) * hop_s, rms)
    else:
        onset = np.zeros_like(times)
        rise = np.zeros_like(times)
        loud = np.ones_like(times)
    return Features(times, hop_s, midi, voiced, onset, rise, _pitch_motion(midi, hop_s), loud)


def decode(f: Features, params: SegmenterParams | None = None) -> list[Note]:
    """Run the HMM over precomputed features and turn the state path into notes."""
    p = params or SegmenterParams()
    times, hop_s, midi = f.times, f.hop_s, f.midi
    pitches = np.arange(p.midi_low, p.midi_high + 1, dtype=float)
    onset = np.clip((1 - p.onset_mix) * f.onset + p.onset_mix * f.rise, 0.0, 1.0)
    log_obs = _log_observations(np.nan_to_num(midi), f.voiced, onset, f.motion, pitches, p)
    # librosa's Viterbi takes probabilities; shift each frame so its best state is 1.
    prob = np.exp(log_obs - log_obs.max(axis=0, keepdims=True))
    trans = _transitions(len(pitches), p)
    init = np.zeros(len(prob))
    init[0] = 0.9
    init[1 : 1 + len(pitches)] = 0.1 / len(pitches)
    states = librosa.sequence.viterbi(prob, trans, p_init=init)

    n_pitch = len(pitches)
    in_note = states > 0
    pitch_idx = np.where(states > n_pitch, states - 1 - n_pitch, states - 1)
    is_attack = (states >= 1) & (states <= n_pitch)

    notes: list[Note] = []
    i = 0
    while i < len(states):
        if not in_note[i]:
            i += 1
            continue
        j = i + 1
        # A note continues while we stay on the same pitch without a fresh attack run.
        while (
            j < len(states)
            and in_note[j]
            and pitch_idx[j] == pitch_idx[i]
            and not (is_attack[j] and not is_attack[j - 1])
        ):
            j += 1
        onset_t, offset_t = times[i], times[j - 1] + hop_s
        if offset_t - onset_t >= p.min_note_s:
            center = _note_pitch(midi[i:j], f.loud[i:j], p.trim_fraction)
            if center is None:
                center = float(pitches[pitch_idx[i]])
            notes.append(Note(onset=float(onset_t), offset=float(offset_t), midi=center))
        i = j
    return notes


def segment(
    track: PitchTrack,
    audio: np.ndarray | None = None,
    sample_rate: int | None = None,
    params: SegmenterParams | None = None,
) -> list[Note]:
    """Notes from a pitch track (plus the audio, for onset and loudness evidence)."""
    f = features(track, audio, sample_rate)
    return [] if f is None else decode(f, params)
