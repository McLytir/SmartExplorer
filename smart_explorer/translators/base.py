from abc import ABC, abstractmethod
from typing import Optional, List


class Translator(ABC):
    @abstractmethod
    def translate_title(self, title: str, target_language: str) -> Optional[str]:
        """
        Translate a short file/folder title into the target language.
        Return None on failure (caller will fall back to original).
        """
        raise NotImplementedError

    def translate_titles(self, titles: List[str], target_language: str) -> List[Optional[str]]:
        """
        Optional batch translation. Default implementation calls translate_title per item.
        Implementations may override for efficiency.
        """
        return [self.translate_title(t, target_language) for t in titles]

    def cache_namespace(self) -> str:
        """
        Identifier for translation cache separation.
        Override when translator configuration (e.g., model) matters.
        """
        return self.__class__.__name__


class IdentityTranslator(Translator):
    def translate_title(self, title: str, target_language: str) -> Optional[str]:
        # No-op translation (useful when API key is missing)
        return title

    def translate_titles(self, titles: List[str], target_language: str) -> List[Optional[str]]:
        return list(titles)

    def cache_namespace(self) -> str:
        return "identity"
