import pytest
from unittest.mock import patch, MagicMock
from backend.shared.ai.gemini import generate_gemini_response, parse_receipt_with_gemini, OCRQuotaExceededError
from backend.core.config import settings


@patch("backend.shared.ai.gemini.get_gemini_client")
@patch("backend.shared.ai.gemini.settings")
def test_primary_text_success(mock_settings, mock_get_client):
    mock_settings.GEMINI_API_KEY = "test_key"
    mock_settings.GEMINI_MODEL = "gemini-3.8-flash"
    mock_settings.GEMINI_FALLBACK_MODEL = "gemini-3.5-flash-lite"

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = "Hello from primary model"
    mock_client.models.generate_content.return_value = mock_resp
    mock_get_client.return_value = mock_client

    res = generate_gemini_response("Say hello")
    assert res == "Hello from primary model"
    assert mock_client.models.generate_content.call_count == 1
    call_args = mock_client.models.generate_content.call_args
    assert call_args.kwargs["model"] == "gemini-3.8-flash"


@patch("backend.shared.ai.gemini.get_gemini_client")
@patch("backend.shared.ai.gemini.settings")
def test_primary_text_429_triggers_fallback_success(mock_settings, mock_get_client):
    mock_settings.GEMINI_API_KEY = "test_key"
    mock_settings.GEMINI_MODEL = "gemini-3.8-flash"
    mock_settings.GEMINI_FALLBACK_MODEL = "gemini-3.5-flash-lite"

    mock_client = MagicMock()
    primary_err = Exception("429 RESOURCE_EXHAUSTED: quota exceeded")
    fallback_resp = MagicMock()
    fallback_resp.text = "Hello from fallback model"

    def side_effect(model, contents, config=None):
        if model == "gemini-3.8-flash":
            raise primary_err
        elif model == "gemini-3.5-flash-lite":
            return fallback_resp
        raise RuntimeError("Unexpected model called")

    mock_client.models.generate_content.side_effect = side_effect
    mock_get_client.return_value = mock_client

    res = generate_gemini_response("Say hello")
    assert res == "Hello from fallback model"
    assert mock_client.models.generate_content.call_count == 2


@patch("backend.shared.ai.gemini.get_gemini_client")
@patch("backend.shared.ai.gemini.settings")
def test_both_text_models_429(mock_settings, mock_get_client):
    mock_settings.GEMINI_API_KEY = "test_key"
    mock_settings.GEMINI_MODEL = "gemini-3.8-flash"
    mock_settings.GEMINI_FALLBACK_MODEL = "gemini-3.5-flash-lite"

    mock_client = MagicMock()
    err = Exception("429 RESOURCE_EXHAUSTED: quota exceeded")
    mock_client.models.generate_content.side_effect = err
    mock_get_client.return_value = mock_client

    with pytest.raises(Exception) as exc_info:
        generate_gemini_response("Say hello")
    assert "429" in str(exc_info.value)
    assert mock_client.models.generate_content.call_count == 2


@patch("backend.shared.ai.gemini.generate_gemini_response")
@patch("os.path.exists", return_value=True)
@patch("PIL.Image.open")
def test_primary_ocr_success(mock_image_open, mock_exists, mock_gen_res):
    mock_gen_res.return_value = '{"vendor_name": "Home Depot", "total_amount": 100.0, "items": []}'
    res = parse_receipt_with_gemini("/tmp/receipt.jpg")
    assert res["vendor_name"] == "Home Depot"
    assert res["total_amount"] == 100.0


@patch("backend.shared.ai.gemini.get_gemini_client")
@patch("backend.shared.ai.gemini.settings")
@patch("os.path.exists", return_value=True)
@patch("PIL.Image.open")
def test_primary_ocr_429_triggers_fallback_ocr_success(mock_image_open, mock_exists, mock_settings, mock_get_client):
    mock_settings.GEMINI_API_KEY = "test_key"
    mock_settings.GEMINI_MODEL = "gemini-3.8-flash"
    mock_settings.GEMINI_FALLBACK_MODEL = "gemini-3.5-flash-lite"

    mock_client = MagicMock()
    fallback_resp = MagicMock()
    fallback_resp.text = '{"vendor_name": "Fallback Hardware", "total_amount": 75.50, "items": []}'

    def side_effect(model, contents, config=None):
        if model == "gemini-3.8-flash":
            raise Exception("429 RESOURCE_EXHAUSTED: quota exceeded")
        elif model == "gemini-3.5-flash-lite":
            return fallback_resp
        raise RuntimeError("Unexpected model called")

    mock_client.models.generate_content.side_effect = side_effect
    mock_get_client.return_value = mock_client

    res = parse_receipt_with_gemini("/tmp/receipt.jpg")
    assert res["vendor_name"] == "Fallback Hardware"
    assert res["total_amount"] == 75.50
    assert mock_client.models.generate_content.call_count == 2


@patch("backend.shared.ai.gemini.get_gemini_client")
@patch("backend.shared.ai.gemini.settings")
@patch("os.path.exists", return_value=True)
@patch("PIL.Image.open")
def test_both_ocr_models_429(mock_image_open, mock_exists, mock_settings, mock_get_client):
    mock_settings.GEMINI_API_KEY = "test_key"
    mock_settings.GEMINI_MODEL = "gemini-3.8-flash"
    mock_settings.GEMINI_FALLBACK_MODEL = "gemini-3.5-flash-lite"

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("429 RESOURCE_EXHAUSTED: quota exceeded")
    mock_get_client.return_value = mock_client

    with pytest.raises(OCRQuotaExceededError) as exc_info:
        parse_receipt_with_gemini("/tmp/receipt.jpg")
    assert "quota exceeded" in str(exc_info.value).lower()
    assert mock_client.models.generate_content.call_count == 2


@patch("backend.shared.ai.gemini.get_gemini_client")
@patch("backend.shared.ai.gemini.settings")
def test_non_retryable_error_does_not_trigger_fallback(mock_settings, mock_get_client):
    mock_settings.GEMINI_API_KEY = "test_key"
    mock_settings.GEMINI_MODEL = "gemini-3.8-flash"
    mock_settings.GEMINI_FALLBACK_MODEL = "gemini-3.5-flash-lite"

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = TypeError("Invalid payload format in client code")
    mock_get_client.return_value = mock_client

    with pytest.raises(TypeError) as exc_info:
        generate_gemini_response("Say hello")
    assert "Invalid payload format" in str(exc_info.value)
    assert mock_client.models.generate_content.call_count == 1
