import os
import re
import subprocess
import sys
from importlib import util
import types
import tempfile
import logging
from pathlib import Path

from open_webui.env import SRC_LOG_LEVELS, PIP_OPTIONS, PIP_PACKAGE_INDEX_OPTIONS
from open_webui.models.functions import Functions
from open_webui.models.tools import Tools

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])


def extract_frontmatter(content):
    """
    Extract frontmatter as a dictionary from the provided content string.
    """
    frontmatter = {}
    frontmatter_started = False
    frontmatter_ended = False
    frontmatter_pattern = re.compile(r"^\s*([a-z_]+):\s*(.*)\s*$", re.IGNORECASE)

    try:
        lines = content.splitlines()
        if len(lines) < 1 or lines[0].strip() != '"""':
            # The content doesn't start with triple quotes
            return {}

        frontmatter_started = True

        for line in lines[1:]:
            if '"""' in line:
                if frontmatter_started:
                    frontmatter_ended = True
                    break

            if frontmatter_started and not frontmatter_ended:
                match = frontmatter_pattern.match(line)
                if match:
                    key, value = match.groups()
                    frontmatter[key.strip()] = value.strip()

    except Exception as e:
        log.exception(f"Failed to extract frontmatter: {e}")
        return {}

    return frontmatter


def replace_imports(content):
    """
    Replace the import paths in the content.
    """
    replacements = {
        "from utils": "from open_webui.utils",
        "from apps": "from open_webui.apps",
        "from main": "from open_webui.main",
        "from config": "from open_webui.config",
    }

    for old, new in replacements.items():
        content = content.replace(old, new)

    return content


def load_tools_module_by_id(toolkit_id, content=None):

    if content is None:
        tool = Tools.get_tool_by_id(toolkit_id)
        if not tool:
            raise Exception(f"Toolkit not found: {toolkit_id}")

        content = tool.content

        content = replace_imports(content)
        Tools.update_tool_by_id(toolkit_id, {"content": content})
    else:
        frontmatter = extract_frontmatter(content)
        # Install required packages found within the frontmatter
        install_frontmatter_requirements(frontmatter.get("requirements", ""))

    module_name = f"tool_{toolkit_id}"
    module = types.ModuleType(module_name)
    sys.modules[module_name] = module

    # Create a temporary file and use it to define `__file__` so
    # that it works as expected from the module's perspective.
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_file.close()
    try:
        path_obj = Path(temp_file.name)
        temp_dir_obj = Path(tempfile.gettempdir())
    
        if not path_obj.resolve().is_relative_to(temp_dir_obj.resolve()):
            raise Exception("Unsafe temporary file path")
    
        with path_obj.open("w", encoding="utf-8") as f:
            f.write(content)
        module.__dict__["__file__"] = temp_file.name
    
        exec(content, module.__dict__)
        frontmatter = extract_frontmatter(content)
        log.info(f"Loaded module: {module.__name__}")
    
        if hasattr(module, "Tools"):
            return module.Tools(), frontmatter
        else:
            raise Exception("No Tools class found in the module")
    except Exception as e:
        log.error(f"Error loading module: {toolkit_id}: {e}")
        del sys.modules[module_name]  # Clean up
        raise e
    finally:
        temp_file_path = Path(temp_file.name).resolve()
        temp_dir_path = Path(tempfile.gettempdir()).resolve()
        
        try:
            temp_file_path.relative_to(temp_dir_path)
            temp_file_path.unlink(missing_ok=True)
        except ValueError:
            log.warning(f"Attempt to unlink unsafe temp file: {temp_file.name}")
        except Exception as e:
            log.warning(f"Failed to cleanup temp file {temp_file.name}: {e}")


def load_function_module_by_id(function_id, content=None):
    if content is None:
        function = Functions.get_function_by_id(function_id)
        if not function:
            raise Exception(f"Function not found: {function_id}")
        content = function.content

        content = replace_imports(content)
        Functions.update_function_by_id(function_id, {"content": content})
    else:
        frontmatter = extract_frontmatter(content)
        install_frontmatter_requirements(frontmatter.get("requirements", ""))

    module_name = f"function_{function_id}"
    module = types.ModuleType(module_name)
    sys.modules[module_name] = module

    # Create a temporary file and use it to define `__file__` so
    # that it works as expected from the module's perspective.
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_file.close()
    try:
        path_obj = Path(temp_file.name)
        temp_dir_obj = Path(tempfile.gettempdir())
    
        if not path_obj.resolve().is_relative_to(temp_dir_obj.resolve()):
            raise Exception("Unsafe temporary file path")
    
        with path_obj.open("w", encoding="utf-8") as f:
            f.write(content)
        module.__dict__["__file__"] = temp_file.name
        
        exec(content, module.__dict__)
        frontmatter = extract_frontmatter(content)
        log.info(f"Loaded module: {module.__name__}")

        # Create appropriate object based on available class type in the module
        if hasattr(module, "Pipe"):
            return module.Pipe(), "pipe", frontmatter
        elif hasattr(module, "Filter"):
            return module.Filter(), "filter", frontmatter
        elif hasattr(module, "Action"):
            return module.Action(), "action", frontmatter
        else:
            raise Exception("No Function class found in the module")
    except Exception as e:
        log.error(f"Error loading module: {function_id}: {e}")
        del sys.modules[module_name]  # Cleanup by removing the module in case of error

        Functions.update_function_by_id(function_id, {"is_active": False})
        raise e
    finally:
        temp_file_path = Path(temp_file.name).resolve()
        temp_dir_path = Path(tempfile.gettempdir()).resolve()
        
        try:
            temp_file_path.relative_to(temp_dir_path)
            temp_file_path.unlink(missing_ok=True)
        except ValueError:
            log.warning(f"Attempt to unlink unsafe temp file: {temp_file.name}")
        except Exception as e:
            log.warning(f"Failed to cleanup temp file {temp_file.name}: {e}")


def install_frontmatter_requirements(requirements: str):
    if requirements:
        try:
            req_list = [req.strip() for req in requirements.split(",")]
            log.info(f"Installing requirements: {' '.join(req_list)}")
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install"]
                + PIP_OPTIONS
                + req_list
                + PIP_PACKAGE_INDEX_OPTIONS
            )
        except Exception as e:
            log.error(f"Error installing packages: {' '.join(req_list)}")
            raise e

    else:
        log.info("No requirements found in frontmatter.")
