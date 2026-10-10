import hashlib
import zipfile

import pytest

from clay_research.datasets import download


def test_every_source_has_checksum_and_license():
    for source in download.SOURCES.values():
        assert len(source.md5) == 32
        assert source.license
        assert source.url.startswith("https://")


def test_md5sum(tmp_path):
    f = tmp_path / "x.bin"
    f.write_bytes(b"clay" * 1000)
    assert download.md5sum(f) == hashlib.md5(b"clay" * 1000).hexdigest()


def test_zip_extract_skips_junk_and_filters_prefixes(tmp_path):
    archive = tmp_path / "set.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("data_by_singer/f1/a.wav", b"keep")
        z.writestr("data_by_vowel/a/a.wav", b"duplicate")
        z.writestr("data_by_singer/.DS_Store", b"junk")
        z.writestr("__MACOSX/data_by_singer/._a.wav", b"junk")
        z.writestr("readme-anon.txt", b"readme")
    out = tmp_path / "out"

    download.extract(archive, out, ("data_by_singer/", "readme-anon.txt"))

    files = sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())
    assert files == ["data_by_singer/f1/a.wav", "readme-anon.txt"]


def test_install_rejects_bad_checksum(tmp_path, monkeypatch):
    source = download.Source(
        name="fake",
        url="https://example.invalid/fake.zip",
        filename="fake.zip",
        md5="0" * 32,
        license="test",
        home="test",
    )
    monkeypatch.setattr(download, "fetch", lambda url, dest: dest.write_bytes(b"not it"))

    with pytest.raises(RuntimeError, match="MD5 mismatch"):
        download.install(source, tmp_path)
    assert not (tmp_path / "fake" / ".complete").exists()
