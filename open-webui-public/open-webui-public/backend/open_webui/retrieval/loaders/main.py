import requests
import logging
import ftfy
import re
import sys
import os
from pathlib import Path

from langchain_community.document_loaders import (
    AzureAIDocumentIntelligenceLoader,
    BSHTMLLoader,
    CSVLoader,
    Docx2txtLoader,
    OutlookMessageLoader,
    PyPDFLoader,
    TextLoader,
    UnstructuredEPubLoader,
    UnstructuredExcelLoader,
    UnstructuredMarkdownLoader,
    UnstructuredPowerPointLoader,
    UnstructuredRSTLoader,
    UnstructuredXMLLoader,
    YoutubeLoader,
)
from langchain_core.documents import Document
from open_webui.env import SRC_LOG_LEVELS, GLOBAL_LOG_LEVEL

logging.basicConfig(stream=sys.stdout, level=GLOBAL_LOG_LEVEL)
log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])

known_source_ext = [
    "go",
    "py",
    "java",
    "sh",
    "bat",
    "ps1",
    "cmd",
    "js",
    "ts",
    "css",
    "cpp",
    "hpp",
    "h",
    "c",
    "cs",
    "sql",
    "log",
    "ini",
    "pl",
    "pm",
    "r",
    "dart",
    "dockerfile",
    "env",
    "php",
    "hs",
    "hsc",
    "lua",
    "nginxconf",
    "conf",
    "m",
    "mm",
    "plsql",
    "perl",
    "rb",
    "rs",
    "db2",
    "scala",
    "bash",
    "swift",
    "vue",
    "svelte",
    "msg",
    "ex",
    "exs",
    "erl",
    "tsx",
    "jsx",
    "hs",
    "lhs",
    "json",
]


class TikaLoader:
    def __init__(self, url, file_path, mime_type=None):
        self.url = url
        self.file_path = file_path
        self.mime_type = mime_type

    def is_safe_url(self, url):
        parsed = urlparse(url)
        allowed_hosts = {"127.0.0.1", "localhost"}
        return (
            parsed.scheme in {"http", "https"} and
            (parsed.hostname in allowed_hosts or not self._is_private_ip(parsed.hostname))
        )

    def _is_private_ip(self, host):
        # Защита от внутренних IP типа 10.x.x.x, 192.168.x.x, и т.д.
        private_prefixes = ("10.", "172.", "192.168.", "0.")
        return any(host.startswith(prefix) for prefix in private_prefixes)

    def load(self) -> list[Document]:
        if not self.is_safe_url(self.url):
            raise ValueError(f"Blocked potentially unsafe URL: {self.url}")

        try:
            file_path = Path(self.file_path).resolve()
            safe_dir = Path("/app/backend/data/uploads").resolve()  # или импортируй из env.py
    
            if not str(file_path).startswith(str(safe_dir)):
                raise ValueError(f"Unsafe file path: {file_path}")
    
            if not file_path.is_file():
                raise ValueError(f"Invalid file path: {file_path}")
    
            if file_path.stat().st_size > 100 * 1024 * 1024:
                raise ValueError(f"File too large: {file_path.stat().st_size} bytes")
    
            with file_path.open("rb") as file:
                data = file.read()
    
            return self.process_file(data)
    
        except (OSError, PermissionError) as e:
            raise ValueError(f"Cannot read file: {e}") from e

        headers = {"Content-Type": self.mime_type} if self.mime_type else {}

        endpoint = self.url.rstrip("/") + "/tika/text"

        try:
            r = requests.put(endpoint, data=data, headers=headers, timeout=5)
        except requests.RequestException as e:
            raise Exception(f"Error calling Tika: {e}") from e

        if r.ok:
            raw_metadata = r.json()
            text = raw_metadata.get("X-TIKA:content", "<No text content found>").strip()

            if "Content-Type" in raw_metadata:
                headers["Content-Type"] = raw_metadata["Content-Type"]

            log.debug("Tika extracted text: %s", text)

            return [Document(page_content=text, metadata=headers)]
        else:
            raise Exception(f"Error calling Tika: {r.status_code} {r.reason}")

class DoclingLoader:
    def __init__(self, url, file_path=None, mime_type=None):
        self.url = url.rstrip("/")
        self.file_path = file_path
        self.mime_type = mime_type

    def load(self) -> list[Document]:
        try:
            file_path = Path(self.file_path).resolve()
            safe_base = Path("/app/backend/data/uploads").resolve()
    
            if not str(file_path).startswith(str(safe_base)):
                raise ValueError("Unsafe file path")
    
            if not file_path.is_file():
                raise ValueError("Invalid file path")
    
            if file_path.stat().st_size > 50 * 1024 * 1024:
                raise ValueError("File too large")
    
            with file_path.open("rb") as f:
                files = {
                    "files": (
                        file_path.name,
                        f,
                        self.mime_type or "application/octet-stream",
                    )
                }
    
                params = {
                    "image_export_mode": "placeholder",
                    "table_mode": "accurate",
                }
    
                endpoint = f"{self.url}/v1alpha/convert/file"
                r = requests.post(endpoint, files=files, data=params, timeout=10)
    
            return self.process_response(r)

        except (OSError, PermissionError) as e:
            raise ValueError(f"Cannot read or send file:")

        if r.ok:
            result = r.json()
            document_data = result.get("document", {})
            text = document_data.get("md_content", "<No text content found>")

            metadata = {"Content-Type": self.mime_type} if self.mime_type else {}

            log.debug("Docling extracted text: %s", text)

            return [Document(page_content=text, metadata=metadata)]
        else:
            error_msg = f"Error calling Docling API: {r.reason}"
            if r.text:
                try:
                    error_data = r.json()
                    if "detail" in error_data:
                        error_msg += f" - {error_data['detail']}"
                except Exception:
                    error_msg += f" - {r.text}"
            raise Exception(f"Error calling Docling: {error_msg}")


class Loader:
    def __init__(self, engine: str = "", **kwargs):
        self.engine = engine
        self.kwargs = kwargs

    def load(
        self, filename: str, file_content_type: str, file_path: str
    ) -> list[Document]:
        loader = self._get_loader(filename, file_content_type, file_path)
        docs = loader.load()

        return [
            Document(
                page_content=ftfy.fix_text(doc.page_content), metadata=doc.metadata
            )
            for doc in docs
        ]

    def _get_loader(self, filename: str, file_content_type: str, file_path: str):
        file_ext = filename.split(".")[-1].lower()

        if self.engine == "tika" and self.kwargs.get("TIKA_SERVER_URL"):
            if file_ext in known_source_ext or (
                file_content_type and file_content_type.find("text/") >= 0
            ):
                loader = TextLoader(file_path, autodetect_encoding=True)
            else:
                loader = TikaLoader(
                    url=self.kwargs.get("TIKA_SERVER_URL"),
                    file_path=file_path,
                    mime_type=file_content_type,
                )
        elif self.engine == "docling" and self.kwargs.get("DOCLING_SERVER_URL"):
            loader = DoclingLoader(
                url=self.kwargs.get("DOCLING_SERVER_URL"),
                file_path=file_path,
                mime_type=file_content_type,
            )
        elif (
            self.engine == "document_intelligence"
            and self.kwargs.get("DOCUMENT_INTELLIGENCE_ENDPOINT") != ""
            and self.kwargs.get("DOCUMENT_INTELLIGENCE_KEY") != ""
            and (
                file_ext in ["pdf", "xls", "xlsx", "docx", "ppt", "pptx"]
                or file_content_type
                in [
                    "application/vnd.ms-excel",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "application/vnd.ms-powerpoint",
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                ]
            )
        ):
            loader = AzureAIDocumentIntelligenceLoader(
                file_path=file_path,
                api_endpoint=self.kwargs.get("DOCUMENT_INTELLIGENCE_ENDPOINT"),
                api_key=self.kwargs.get("DOCUMENT_INTELLIGENCE_KEY"),
            )
        else:
            if file_ext == "pdf":
                loader = PyPDFLoader(
                    file_path, extract_images=self.kwargs.get("PDF_EXTRACT_IMAGES")
                )
            elif file_ext == "csv":
                loader = CSVLoader(file_path, autodetect_encoding=True)
            elif file_ext == "rst":
                loader = UnstructuredRSTLoader(file_path, mode="elements")
            elif file_ext == "xml":
                loader = UnstructuredXMLLoader(file_path)
            elif file_ext in ["htm", "html"]:
                loader = BSHTMLLoader(file_path, open_encoding="unicode_escape")
            elif file_ext == "md":
                loader = TextLoader(file_path, autodetect_encoding=True)
            elif file_content_type == "application/epub+zip":
                loader = UnstructuredEPubLoader(file_path)
            elif (
                file_content_type
                == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                or file_ext == "docx"
            ):
                loader = Docx2txtLoader(file_path)
            elif file_content_type in [
                "application/vnd.ms-excel",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ] or file_ext in ["xls", "xlsx"]:
                loader = UnstructuredExcelLoader(file_path)
            elif file_content_type in [
                "application/vnd.ms-powerpoint",
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ] or file_ext in ["ppt", "pptx"]:
                loader = UnstructuredPowerPointLoader(file_path)
            elif file_ext == "msg":
                loader = OutlookMessageLoader(file_path)
            elif file_ext in known_source_ext or (
                file_content_type and file_content_type.find("text/") >= 0
            ):
                loader = TextLoader(file_path, autodetect_encoding=True)
            else:
                loader = TextLoader(file_path, autodetect_encoding=True)

        return loader
