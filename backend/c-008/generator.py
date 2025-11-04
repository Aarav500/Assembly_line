import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests

TOOLS_DIR = os.path.join(os.path.dirname(__file__), "tools")
JAR_PATH = os.path.join(TOOLS_DIR, "openapi-generator-cli.jar")
META_PATH = os.path.join(TOOLS_DIR, ".openapi-generator.version")

class GenerationError(Exception):
    pass

@dataclass
class SDKGenerator:
    version: Optional[str] = None

    def ensure_cli(self) -> str:
        os.makedirs(TOOLS_DIR, exist_ok=True)

        # If user specified version, ensure that version is installed
        if self.version:
            if self._jar_exists_for_version(self.version):
                return JAR_PATH
            self._download_cli(self.version)
            return JAR_PATH

        # If jar exists, return
        if os.path.isfile(JAR_PATH):
            return JAR_PATH

        # Otherwise resolve latest version and download
        version = self._resolve_latest_cli_version()
        if not version:
            raise GenerationError("Unable to resolve latest openapi-generator-cli version")
        self._download_cli(version)
        return JAR_PATH

    def _jar_exists_for_version(self, version: str) -> bool:
        if not os.path.isfile(JAR_PATH) or not os.path.isfile(META_PATH):
            return False
        try:
            with open(META_PATH, "r", encoding="utf-8") as f:
                current = f.read().strip()
            return current == version
        except Exception:
            return False

    def _resolve_latest_cli_version(self) -> Optional[str]:
        # Try env override first
        env_v = os.getenv("OPENAPI_GENERATOR_VERSION")
        if env_v:
            return env_v.strip()
        # Fetch maven metadata
        url = "https://repo1.maven.org/maven2/org/openapitools/openapi-generator-cli/maven-metadata.xml"
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            root = ET.fromstring(r.text)
            latest = root.findtext("./versioning/release") or root.findtext("./versioning/latest")
            if latest:
                return latest.strip()
        except Exception:
            return None
        return None

    def _download_cli(self, version: str) -> None:
        jar_url = (
            f"https://repo1.maven.org/maven2/org/openapitools/openapi-generator-cli/{version}/"
            f"openapi-generator-cli-{version}.jar"
        )
        tmp_path = os.path.join(TOOLS_DIR, f"openapi-generator-cli-{version}.jar.tmp")
        try:
            with requests.get(jar_url, stream=True, timeout=120) as r:
                r.raise_for_status()
                total = int(r.headers.get("Content-Length", "0"))
                downloaded = 0
                with open(tmp_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 128):
                        if not chunk:
                            continue
                        f.write(chunk)
                        downloaded += len(chunk)
            # Move into place atomically
            if os.path.exists(JAR_PATH):
                os.remove(JAR_PATH)
            os.replace(tmp_path, JAR_PATH)
            with open(META_PATH, "w", encoding="utf-8") as f:
                f.write(version)
        except Exception as e:
            # Cleanup tmp
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            raise GenerationError(f"Failed to download openapi-generator-cli {version}: {e}")

    def _props_dict_to_param(self, d: Dict[str, Any]) -> str:
        def to_str(v: Any) -> str:
            if isinstance(v, bool):
                return "true" if v else "false"
            return str(v)
        parts: List[str] = []
        for k, v in d.items():
            if v is None:
                continue
            parts.append(f"{k}={to_str(v)}")
        return ",".join(parts)

    def _lang_to_generator(self, language: str, ts_flavor: Optional[str]) -> Tuple[str, Dict[str, Any]]:
        language = language.lower()
        props: Dict[str, Any] = {}
        if language == "python":
            return "python", props
        if language == "typescript":
            if ts_flavor == "axios":
                return "typescript-axios", props
            return "typescript-fetch", props
        if language == "go":
            return "go", props
        if language == "java":
            return "java", props
        raise GenerationError(f"Unsupported language: {language}")

    def generate_language(
        self,
        language: str,
        spec_path: str,
        output_dir: str,
        additional_properties: Optional[Dict[str, Any]] = None,
        ts_flavor: Optional[str] = None,
    ) -> Dict[str, Any]:
        jar = self.ensure_cli()
        generator_name, base_props = self._lang_to_generator(language, ts_flavor)

        # Merge additional properties with base props
        add_props: Dict[str, Any] = {}
        add_props.update(base_props)
        if additional_properties:
            add_props.update(additional_properties)

        # Ensure some sane defaults if not provided
        if language == "python":
            add_props.setdefault("packageName", "openapi_client")
            add_props.setdefault("projectName", "openapi_client")
        elif language == "typescript":
            add_props.setdefault("supportsES6", True)
            # packageName is npmName in generator
            add_props.setdefault("npmName", "api-client")
        elif language == "go":
            add_props.setdefault("packageName", "apiclient")
        elif language == "java":
            add_props.setdefault("groupId", "com.example")
            add_props.setdefault("artifactId", "api-client")
            add_props.setdefault("artifactVersion", "1.0.0")

        # Build CLI command
        cmd = [
            "java",
            "-jar",
            jar,
            "generate",
            "-g",
            generator_name,
            "-i",
            spec_path,
            "-o",
            output_dir,
            "-p",
            self._props_dict_to_param(add_props),
        ]

        # Prefer to skip validating spec on network
        # cmd += ["--skip-validate-spec"]  # optional

        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
                text=True,
            )
        except FileNotFoundError:
            raise GenerationError(
                "Java runtime not found. Ensure 'java' is installed and available in PATH."
            )
        except Exception as e:
            raise GenerationError(f"Failed to run generator: {e}")

        if proc.returncode != 0:
            raise GenerationError(
                f"openapi-generator-cli failed (exit {proc.returncode}):\n{proc.stdout[:5000]}"
            )

        # Return some basic info
        return {
            "language": language,
            "generator": generator_name,
            "output": output_dir,
            "logTail": proc.stdout[-1000:],
        }

