import io

import pytest
from PIL import Image

from backend import settings, uploads
from backend.uploads import UploadError, clean_name, prepare


def png(size=(8, 8)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, "white").save(buffer, "PNG")
    return buffer.getvalue()


def jpeg() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(buffer, "JPEG")
    return buffer.getvalue()


def webp() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(buffer, "WEBP")
    return buffer.getvalue()


def refused(files) -> UploadError:
    with pytest.raises(UploadError) as caught:
        prepare(files)
    return caught.value


def test_one_text_file_is_the_specification_as_it_is():
    prepared = prepare([("spec.md", b"\xef\xbb\xbf# spec: Rear Lamp\r\n\r\nA lamp.\r\n")])
    assert prepared.spec_text == "# spec: Rear Lamp\n\nA lamp.\n"
    assert prepared.image is None
    assert prepared.files == [{"name": "spec.md", "role": "specification", "bytes": 33}]


def test_several_text_files_are_joined_in_upload_order_under_a_heading_each():
    prepared = prepare([("b.md", b"second"), ("a.txt", b"first")])
    assert prepared.spec_text == "## b.md\n\nsecond\n\n## a.txt\n\nfirst\n"


@pytest.mark.parametrize("make,ext", [(png, "png"), (jpeg, "jpg"), (webp, "webp")])
def test_an_image_is_recognised_by_its_content_whatever_its_name(make, ext):
    prepared = prepare([("notes.txt", make())])
    assert prepared.image_ext == ext and prepared.spec_text is None
    assert prepared.files[0]["role"] == "drawing"


def test_specification_and_drawing_together():
    prepared = prepare([("spec.md", b"text"), ("view.png", png())])
    assert prepared.spec_text == "text\n" and prepared.image_ext == "png"


def test_the_case_folder_has_the_names_the_pipeline_looks_for(tmp_path):
    from ai_agent.inputs import find_inputs

    prepare([("../../etc/passwd.md", b"text"), ("evil name.png", png())]).write(tmp_path / "case")
    found = find_inputs(tmp_path / "case")
    assert found.text_path.name == "spec.md" and found.image_path.name == "drawing.png"
    assert sorted(p.name for p in (tmp_path / "case").iterdir()) == ["drawing.png", "spec.md"]


def test_nothing_uploaded_is_refused():
    assert refused([]).status == 400


def test_a_second_drawing_is_refused():
    error = refused([("a.png", png()), ("b.png", png())])
    assert error.status == 400 and "only one drawing" in error.detail


def test_pdf_and_word_files_are_refused_with_a_clear_message():
    assert refused([("datasheet.md", b"%PDF-1.7 ...")]).status == 415
    error = refused([("bom.docx", b"PK\x03\x04 ...")])
    assert error.status == 415 and "PDF and Word" in error.detail


def test_binary_and_non_utf8_content_is_not_text():
    assert refused([("a.txt", b"abc\x00def")]).status == 415
    assert refused([("a.txt", b"caf\xe9")]).status == 415


def test_a_damaged_image_is_refused():
    error = refused([("a.png", png()[:40])])
    assert error.status == 400 and "damaged" in error.detail


def test_empty_and_oversize_files_are_refused(monkeypatch):
    assert refused([("a.md", b"")]).status == 400
    assert refused([("a.md", b"x" * (settings.MAX_FILE_BYTES + 1))]).status == 413
    monkeypatch.setattr(uploads, "MAX_TEXT_CHARS", 10)
    assert refused([("a.md", b"x" * 11)]).status == 413


def test_text_files_that_are_only_white_space_do_not_count():
    assert refused([("a.md", b"  \n ")]).status == 400
    assert prepare([("a.md", b" \n"), ("v.png", png())]).spec_text is None


def test_too_many_files_are_refused():
    assert refused([(f"{i}.md", b"x") for i in range(settings.MAX_FILES + 1)]).status == 400


def test_file_names_are_cleaned_before_they_are_printed():
    assert clean_name("../../a/b/Spec v2.md") == "Spec v2.md"
    assert clean_name("x\\y\\<script>.md") == "script_.md"
    assert clean_name("") == "file"
    assert len(clean_name("a" * 300)) == 80
