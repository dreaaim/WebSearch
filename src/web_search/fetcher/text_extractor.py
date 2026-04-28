from typing import Optional
from dataclasses import dataclass


@dataclass
class TextExtractionResult:
    text: str
    success: bool
    error_reason: Optional[str] = None


class TextExtractor:
    def __init__(self, min_text_length: int = 100, max_text_length: int = 100000):
        self.min_text_length = min_text_length
        self.max_text_length = max_text_length

    def extract_text(self, html_content: str) -> TextExtractionResult:
        if not html_content or not html_content.strip():
            return TextExtractionResult(
                text="",
                success=False,
                error_reason="Empty or None HTML content"
            )

        try:
            import trafilatura
            text = trafilatura.extract(
                html_content,
                include_comments=False,
                include_tables=True,
                favor_recall=True
            )
            if text and len(text.strip()) >= self.min_text_length:
                text = text[:self.max_text_length]
                return TextExtractionResult(text=text, success=True)
        except ImportError:
            pass
        except Exception:
            pass

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, "html.parser")

            for tag in soup.find_all(["script", "style", "nav", "header", "footer", "aside"]):
                tag.decompose()

            for tag in soup.find_all(["nav", "header", "footer", "aside"]):
                tag.decompose()

            main_content = soup.find("main") or soup.find("article") or soup.find("body")
            if main_content:
                soup = main_content

            text = soup.get_text(separator="\n", strip=True)
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            text = "\n".join(lines)

            if len(text) < self.min_text_length:
                return TextExtractionResult(
                    text="",
                    success=False,
                    error_reason=f"Extracted text too short: {len(text)} chars"
                )

            text = text[:self.max_text_length]
            return TextExtractionResult(text=text, success=True)

        except ImportError:
            return TextExtractionResult(
                text="",
                success=False,
                error_reason="Neither trafilatura nor BeautifulSoup available"
            )
        except Exception as e:
            return TextExtractionResult(
                text="",
                success=False,
                error_reason=f"Extraction failed: {str(e)}"
            )


def extract_text(html_content: str) -> str:
    extractor = TextExtractor()
    result = extractor.extract_text(html_content)
    return result.text