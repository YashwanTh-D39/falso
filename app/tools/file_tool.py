from __future__ import annotations

import asyncio
import glob as glob_module
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, ClassVar

from app.tools.base import Tool, ToolResult
from app.tools.registry import ToolRegistry
from config.settings import settings

logger = logging.getLogger(__name__)

# Dedicated, bounded lane for file operations. A recursive search can scan
# entire folders and hold a worker for seconds; on the default pool that would
# starve every other thread-backed operation in the app, so file work gets its
# own 2-worker executor instead.
_FILE_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="falso-file-tool")


def _allowed_bases() -> list[Path]:
    home = Path.home()
    bases = [
        home / "Documents",
        home / "Desktop",
        home / "Downloads",
    ]
    if settings.file_tool_workspace:
        bases.append(Path(settings.file_tool_workspace).resolve())
    return bases


def _relative_bases() -> list[Path]:
    """Order bases for relative-path resolution: the configured workspace
    takes priority, then the standard user folders."""
    bases = _allowed_bases()
    if not settings.file_tool_workspace:
        return bases
    workspace = Path(settings.file_tool_workspace).resolve()
    return [workspace] + [b for b in bases if b.resolve() != workspace]


def _check_allowed(path: Path) -> Path:
    resolved = path.resolve()
    # Reject symlinks: a symlink inside an allowed directory could point
    # outside the sandbox. path.resolve() follows symlinks, so we compare
    # the resolved result to the original to detect them.
    if path.exists() and path.is_symlink():
        raise PermissionError(
            f"Access denied: symlinks are not allowed ({path})"
        )
    for base in _allowed_bases():
        try:
            resolved.relative_to(base.resolve())
            return resolved
        except ValueError:
            continue
    raise PermissionError(
        f"Access denied. Path must be within one of: "
        f"{[str(b) for b in _allowed_bases()]}"
    )



def _resolve_path(user_path: str) -> Path:
    p = Path(user_path)

    if user_path.startswith("~"):
        return _check_allowed(p.expanduser())

    if p.is_absolute():
        return _check_allowed(p)

    for base in _relative_bases():
        try:
            return _check_allowed(base / p)
        except PermissionError:
            continue

    raise PermissionError(
        f"Access denied: '{user_path}' is not in an allowed directory"
    )


@ToolRegistry.register
class FileTool(Tool):
    name = "file"
    description = (
        "Read, write, append, create folders, list, search, rename, "
        "or delete text files. Restricted to Documents, Desktop, "
        "Downloads, and configured workspace."
    )
    parameters: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "enum": [
                    "read", "write", "append", "mkdir",
                    "list", "search", "rename", "delete",
                ],
                "description": (
                    "Operation: read | write | append | mkdir | "
                    "list | search | rename | delete"
                ),
            },
            "path": {
                "type": "string",
                "description": (
                    "Target file or folder path "
                    "(relative or absolute within allowed directories)"
                ),
            },
            "content": {
                "type": "string",
                "description": "Text content for write / append commands",
            },
            "new_name": {
                "type": "string",
                "description": "New path for rename command",
            },
            "pattern": {
                "type": "string",
                "description": "Glob pattern for search command (e.g. *.txt, report*)",
            },
            "confirmed": {
                "type": "boolean",
                "description": "Set to true to confirm a delete operation",
            },
        },
        "required": ["command"],
    }

    _last_filename: str | None = None
    _CONTENT_SEPS: ClassVar[list[str]] = [" to ", " into ", " in ", " with ", " as "]

    @classmethod
    def _default_path(cls) -> str:
        return settings.file_tool_workspace or "."

    @classmethod
    def _strip_path_noise(cls, raw: str) -> str:
        return re.sub(
            r'^(?:the|that|this|a|an)\s+(?:file\s+|folder\s+|directory\s+)?(?:called\s+)?',
            '', raw,
        ).strip()

    @classmethod
    def _extract_quoted(cls, text: str) -> tuple[str | None, str]:
        m = re.search(r'"([^"]*)"|\'([^\']*)\'', text)
        if m:
            content = m.group(1) or m.group(2)
            cleaned = text.replace(m.group(0), '').strip()
            return content, cleaned
        return None, text

    @classmethod
    def _strip_content_labels(cls, text: str) -> str:
        return re.sub(
            r'^(?:the\s+)?(?:content|text)\s+',
            '', text, flags=re.IGNORECASE,
        ).strip()

    @classmethod
    def _split_content_file(cls, text: str, verb: str) -> tuple[str | None, str | None]:
        """Split 'write <content> to <file>' or 'create <file> with <content>' into (content, filename).
        Returns (content, filename) or (None, None)."""
        lower = text.lower()
        best_pos = len(text)
        best_sep = None
        for sep in cls._CONTENT_SEPS:
            pos = lower.find(sep)
            if pos != -1 and pos < best_pos:
                best_pos = pos
                best_sep = sep
        if best_sep is None:
            return None, None
        before = text[len(verb):best_pos].strip()
        after = text[best_pos + len(best_sep):].strip()
        if not before and not after:
            return None, None
        # "create <file> with <content>" / "edit <file> to <content>": path=X, content=Y
        # "write <content> to <file>" / "append <content> to <file>": content=X, path=Y
        if verb in ('create', 'make', 'new', 'edit', 'change') and best_sep in (' with ', ' to ', ' into '):
            return cls._strip_content_labels(after) or None, before or None
        return before or None, cls._strip_content_labels(after) or None

    @classmethod
    def _resolve_pronoun(cls, context: Any = None) -> str | None:
        candidates = [context.last_filename if context else None, cls._last_filename]
        for c in candidates:
            if c:
                return c
        return None

    @classmethod
    def match_prompt(cls, prompt: str, context: Any = None) -> dict | None:
        prompt_stripped = prompt.strip()
        prompt_lower = prompt_stripped.lower()

        file_keywords = [
            'file', 'folder', 'directory', 'read', 'write', 'create', 'delete',
            'remove', 'rename', 'move', 'list', 'open', 'show', 'cat', 'make',
            'mkdir', 'append', 'add', 'search', 'find', 'new', 'copy',
            'ls', 'dir', 'display', 'content', 'text', 'erase', 'put', 'rm',
            'edit', 'change', 'replace', 'save', 'modify', 'copy',
        ]
        if not any(re.search(r'\b' + re.escape(kw) + r'\b', prompt_lower) for kw in file_keywords):
            logger.debug("FileTool: no keyword match — skipping")
            return None

        logger.debug("FileTool: matching prompt=%r", prompt_stripped)

        # --- Extract quoted content upfront ---
        quoted_content, parse_text = cls._extract_quoted(prompt_stripped)
        if quoted_content:
            logger.debug("FileTool: extracted quoted content=%r", quoted_content)

        kwargs: dict = {}

        def store_path(path: str) -> None:
            clean = cls._strip_path_noise(path) if path else ''
            if clean:
                cls._last_filename = clean
                kwargs['path'] = clean
                logger.debug("FileTool: store_path set path=%r", clean)
            elif cls._last_filename:
                kwargs['path'] = cls._last_filename
                logger.debug("FileTool: store_path reused _last_filename=%r", cls._last_filename)
            elif context and context.last_filename:
                kwargs['path'] = context.last_filename
                logger.debug("FileTool: store_path reused context.last_filename=%r", context.last_filename)

        # --- Pronoun resolution ---
        has_pronoun = bool(re.search(
            r'\b(that file|the previous file|same file|this file|it)\b', prompt_lower,
        ))
        resolved_file = cls._resolve_pronoun(context) if has_pronoun else None
        if resolved_file:
            logger.debug("FileTool: resolved pronoun -> %r", resolved_file)

        # --- List / Ls / Dir ---
        if re.search(r'\b(list|ls|dir)\b', prompt_lower) or re.match(
            r'show\s+(?:me\s+)?(?:the\s+)?(?:files|directory|folder|contents)',
            prompt_lower,
        ):
            kwargs['command'] = 'list'
            kwargs['path'] = cls._default_path()
            logger.debug("FileTool: intent=list path=%r", kwargs['path'])
            return kwargs

        # --- Mkdir ---
        m = re.match(
            r'(?:create|make|new)\s+(?:a\s+)?(?:folder|directory)\s+(.+)|mkdir\s+(.+)',
            parse_text, re.IGNORECASE,
        )
        if m:
            kwargs['command'] = 'mkdir'
            kwargs['path'] = (m.group(1) or m.group(2)).strip()
            logger.debug("FileTool: intent=mkdir path=%r", kwargs['path'])
            return kwargs

        # --- Copy / Rename / Move ---
        m = re.match(
            r'(?:copy|rename|move)\s+(.+?)\s+to\s+(.+)',
            parse_text, re.IGNORECASE,
        )
        if m:
            kwargs['command'] = 'rename'
            kwargs['path'] = cls._strip_path_noise(m.group(1).strip())
            kwargs['new_name'] = m.group(2).strip()
            store_path(kwargs['path'])
            logger.debug("FileTool: intent=rename path=%r new_name=%r",
                         kwargs['path'], kwargs['new_name'])
            return kwargs

        # --- Relative reference handler (before delete/edit/search/write) ---
        if has_pronoun and resolved_file:
            if re.search(r'\b(delete|remove|erase|rm)\b', prompt_lower):
                kwargs['command'] = 'delete'
                kwargs['path'] = resolved_file
                kwargs['confirmed'] = bool(re.search(
                    r'\b(yes|confirm|proceed|go ahead|sure)\b', prompt_lower,
                ))
                logger.debug("FileTool: intent=delete (pronoun) path=%r confirmed=%r",
                             kwargs['path'], kwargs['confirmed'])
                return kwargs
            if re.search(r'\b(read|open|show|cat|display)\b', prompt_lower):
                kwargs['command'] = 'read'
                kwargs['path'] = resolved_file
                logger.debug("FileTool: intent=read (pronoun) path=%r", kwargs['path'])
                return kwargs
            if re.search(r'\b(write|put|append|add|create|make|new|edit|change)\b', prompt_lower):
                is_append = bool(re.match(r'(append|add)\b', prompt_lower))
                verb_match = re.match(r'(write|put|append|add|create|make|new|edit|change)\b', prompt_lower)
                verb = verb_match.group(1) if verb_match else None
                kwargs['command'] = 'append' if is_append else 'write'
                kwargs['path'] = resolved_file

                # Strip verb and pronoun, then find content after separators
                remaining = parse_text
                if verb:
                    remaining = re.sub(r'^' + re.escape(verb) + r'\s+', '', remaining, flags=re.IGNORECASE).strip()
                for pw in ('it', 'that', 'this file', 'the previous file', 'same file', 'the file', 'this'):
                    if remaining.lower().startswith(pw):
                        remaining = remaining[len(pw):].strip()
                        break
                # Remaining may start with "to", "as", "in", "with" etc.
                for sw in ('to', 'as', 'in', 'with', 'into'):
                    if remaining.lower().startswith(sw + ' '):
                        remaining = remaining[len(sw):].strip()
                        break
                content = remaining
                for sep in cls._CONTENT_SEPS:
                    pos = remaining.lower().find(sep)
                    if pos != -1:
                        content = remaining[:pos].strip()
                        after = remaining[pos + len(sep):].strip()
                        # If the part after sep looks like a file path, keep resolved_file
                        if after:
                            logger.debug("FileTool: pronoun content split at sep=%r content=%r after=%r",
                                         sep.strip(), content, after)
                            # Only update path if the prompt specified a different file
                            if not any(after.lower().startswith(p) for p in ('it', 'that', 'this')):
                                pass  # Keep resolved_file
                        break

                kwargs['content'] = quoted_content or content or ''
                logger.debug("FileTool: intent=write (pronoun) path=%r content=%r",
                             kwargs['path'], kwargs['content'])
                return kwargs

        # --- Edit handler (e.g. "edit hello.txt to new content", "edit it as hello falso") ---
        m = re.match(
            r'(?:edit|change|modify)\s+(.+?)\s+(?:to|into|as)\s+(.+)',
            parse_text, re.IGNORECASE,
        )
        if m:
            edit_path = m.group(1).strip()
            edit_content = m.group(2).strip()

            # If edit_content contains " in <file>", split it out
            nested = re.match(r'(.+?)\s+in\s+(.+)', edit_content, re.IGNORECASE)
            if nested:
                edit_content = nested.group(1).strip()
                edit_path = nested.group(2).strip()
            elif re.match(r'(.+?)\s+with\s+(.+)', edit_content, re.IGNORECASE):
                nested = re.match(r'(.+?)\s+with\s+(.+)', edit_content, re.IGNORECASE)
                edit_content = nested.group(1).strip()
                edit_path = nested.group(2).strip()

            if edit_path.lower() in ('it', 'that', 'this', 'the file', 'the previous file', 'same file'):
                resolved = cls._resolve_pronoun(context)
                if resolved:
                    edit_path = resolved
                else:
                    edit_path = cls._strip_path_noise(edit_path)
            else:
                edit_path = cls._strip_path_noise(edit_path)
            kwargs['command'] = 'write'
            store_path(edit_path)
            kwargs['content'] = quoted_content or cls._strip_content_labels(edit_content)
            logger.debug("FileTool: intent=edit path=%r content=%r",
                         kwargs['path'], kwargs['content'])
            return kwargs

        # --- Replace handler (handles "replace <content> in <file>" and "replace <file> with <content>") ---
        m = re.match(
            r'replace\s+(.+?)\s+in\s+(.+)',
            parse_text, re.IGNORECASE,
        )
        if m:
            kwargs['command'] = 'write'
            store_path(m.group(2).strip())
            kwargs['content'] = quoted_content or m.group(1).strip()
            logger.debug("FileTool: intent=replace (content-in-file) path=%r content=%r",
                         kwargs['path'], kwargs['content'])
            return kwargs

        m = re.match(
            r'replace\s+(.+?)\s+with\s+(.+)',
            parse_text, re.IGNORECASE,
        )
        if m:
            kwargs['command'] = 'write'
            store_path(cls._strip_path_noise(m.group(1).strip()))
            kwargs['content'] = quoted_content or m.group(2).strip()
            logger.debug("FileTool: intent=replace (file-with-content) path=%r content=%r",
                         kwargs['path'], kwargs['content'])
            return kwargs

        # --- Edit <file> alone (no content) → read so user can see what to change ---
        m = re.match(
            r'(?:edit|change|modify)\s+(.+)',
            parse_text, re.IGNORECASE,
        )
        if m:
            kwargs['command'] = 'read'
            store_path(m.group(1).strip())
            logger.debug("FileTool: intent=edit (read) path=%r", kwargs['path'])
            return kwargs

        # --- Delete / Remove ---
        m = re.match(
            r'(?:delete|remove|rm|erase)\s+(.+?)(?:\s+(?:yes|please|now|it|the\s+file))?\s*$',
            parse_text, re.IGNORECASE,
        )
        if not m:
            m = re.match(
                r'(?:delete|remove|rm|erase)\s+(.+)',
                parse_text, re.IGNORECASE,
            )
        if m:
            kwargs['command'] = 'delete'
            store_path(m.group(1).strip())
            kwargs['confirmed'] = bool(re.search(
                r'\b(yes|confirm|proceed|go ahead|sure|delete it|remove it)\b',
                prompt_lower,
            ))
            logger.debug("FileTool: intent=delete path=%r confirmed=%r",
                         kwargs.get('path'), kwargs['confirmed'])
            return kwargs

        # --- Search / Find ---
        m = re.match(
            r'(?:search|find)\s+(?:for\s+)?(.+)',
            parse_text, re.IGNORECASE,
        )
        if m:
            kwargs['command'] = 'search'
            kwargs['pattern'] = m.group(1).strip()
            logger.debug("FileTool: intent=search pattern=%r", kwargs['pattern'])
            return kwargs

        # --- Write / Append / Save / Replace: extract content and filename ---
        verb_match = re.match(
            r'(write|put|append|add|create|make|new|save|replace)\b',
            prompt_lower,
        )
        verb = verb_match.group(1) if verb_match else None
        is_append = verb in ('append', 'add')

        if verb:
            content, filename = cls._split_content_file(parse_text, verb)
            if content or filename:
                kwargs['command'] = 'append' if is_append else 'write'
                if filename:
                    store_path(filename)
                else:
                    store_path('')
                kwargs['content'] = quoted_content or content or ''
                logger.debug("FileTool: intent=%s path=%r content=%r",
                             kwargs['command'], kwargs.get('path'), kwargs['content'])
                return kwargs

        # --- Read / Open / Show / Cat / Display ---
        m = re.match(
            r'(?:read|open|display|cat|show(?:\s+me)?)\s+(.+)',
            parse_text, re.IGNORECASE,
        )
        if m:
            kwargs['command'] = 'read'
            store_path(m.group(1).strip())
            logger.debug("FileTool: intent=read path=%r", kwargs['path'])
            return kwargs

        # --- Save / Write / Create file (no content) ---
        m = re.match(
            r'(?:create|make|write|new|save)\s+(?:a\s+)?(?:file\s+(?:called\s+)?)?(.+)',
            parse_text, re.IGNORECASE,
        )
        if m:
            kwargs['command'] = 'write'
            store_path(m.group(1).strip())
            kwargs['content'] = quoted_content or ''
            logger.debug("FileTool: intent=write (fallback) path=%r", kwargs['path'])
            return kwargs

        logger.debug("FileTool: no pattern matched — returning None")
        return None

    async def execute(
        self,
        command: str = "",
        path: str = "",
        content: str = "",
        new_name: str = "",
        pattern: str = "",
        confirmed: bool = False,
        **kwargs,
    ) -> ToolResult:
        # All filesystem work is blocking; run it in the dedicated file-tool
        # executor so the event loop never stalls and the default thread pool
        # is never consumed by long folder scans.
        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                _FILE_EXECUTOR,
                self._dispatch,
                command, path, content, new_name, pattern, confirmed,
            )
        except PermissionError as e:
            return ToolResult(success=False, error=str(e))
        except FileNotFoundError as e:
            return ToolResult(success=False, error=str(e))
        except IsADirectoryError as e:
            return ToolResult(success=False, error=str(e))
        except NotADirectoryError as e:
            return ToolResult(success=False, error=str(e))
        except OSError as e:
            return ToolResult(success=False, error=f"File system error: {e}")
        except Exception as e:
            logger.exception("FileTool unhandled error")
            return ToolResult(success=False, error=str(e))

    def _dispatch(
        self,
        command: str,
        path: str,
        content: str,
        new_name: str,
        pattern: str,
        confirmed: bool,
    ) -> ToolResult:
        if command == "read":
            return self._read(path)
        elif command == "write":
            return self._write(path, content)
        elif command == "append":
            return self._append(path, content)
        elif command == "mkdir":
            return self._mkdir(path)
        elif command == "list":
            return self._list(path)
        elif command == "search":
            return self._search(pattern)
        elif command == "rename":
            return self._rename(path, new_name)
        elif command == "delete":
            return self._delete(path, confirmed)
        else:
            return ToolResult(
                success=False,
                error=f"Unknown command: '{command}'",
            )

    def _read(self, path: str) -> ToolResult:
        if not path:
            return ToolResult(success=False, error="path is required")
        p = _resolve_path(path)
        if not p.exists():
            return ToolResult(success=False, error=f"File not found: {path}")
        if not p.is_file():
            return ToolResult(success=False, error=f"Not a file: {path}")
        size = p.stat().st_size
        if size > settings.max_file_read_bytes:
            return ToolResult(
                success=False,
                error=(
                    f"File too large to read ({size} bytes). "
                    f"Maximum is {settings.max_file_read_bytes} bytes."
                ),
            )
        try:
            text = p.read_text(encoding="utf-8")
            return ToolResult(success=True, data={"content": text, "path": str(p)})
        except UnicodeDecodeError:
            return ToolResult(
                success=False,
                error=f"Cannot read '{path}': not a text file or unsupported encoding",
            )

    def _write(self, path: str, content: str) -> ToolResult:
        if not path:
            return ToolResult(success=False, error="path is required")
        if len(content) > settings.max_file_write_bytes:
            return ToolResult(
                success=False,
                error=(
                    f"Content too large ({len(content)} chars). "
                    f"Maximum is {settings.max_file_write_bytes} chars."
                ),
            )
        p = _resolve_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return ToolResult(
            success=True,
            data={"message": f"Written {len(content)} characters to {p.name}", "path": str(p)},
        )

    def _append(self, path: str, content: str) -> ToolResult:
        if not path:
            return ToolResult(success=False, error="path is required")
        p = _resolve_path(path)
        if not p.exists():
            return ToolResult(success=False, error=f"File not found: {path}")
        if not p.is_file():
            return ToolResult(success=False, error=f"Not a file: {path}")
        size = p.stat().st_size
        if size + len(content) > settings.max_file_write_bytes:
            return ToolResult(
                success=False,
                error=(
                    f"Append would exceed the {settings.max_file_write_bytes} "
                    f"byte write limit ({size + len(content)} bytes)."
                ),
            )
        with p.open("a", encoding="utf-8") as f:
            f.write(content)
        return ToolResult(
            success=True,
            data={"message": f"Appended {len(content)} characters to {p.name}", "path": str(p)},
        )

    def _mkdir(self, path: str) -> ToolResult:
        if not path:
            return ToolResult(success=False, error="path is required")
        p = _resolve_path(path)
        p.mkdir(parents=True, exist_ok=True)
        return ToolResult(
            success=True,
            data={"message": f"Folder ready: {p}", "path": str(p)},
        )

    def _list(self, path: str) -> ToolResult:
        if not path:
            path = "."
        p = _resolve_path(path)
        if not p.is_dir():
            return ToolResult(success=False, error=f"Not a directory: {path}")
        items = []
        truncated = False
        for entry in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            if len(items) >= settings.max_list_items:
                truncated = True
                break
            items.append(
                {
                    "name": entry.name,
                    "type": "directory" if entry.is_dir() else "file",
                    "size": entry.stat().st_size if entry.is_file() else None,
                }
            )
        data = {"path": str(p), "items": items}
        if truncated:
            data["truncated"] = True
        return ToolResult(
            success=True,
            data=data,
        )

    def _search(self, pattern: str) -> ToolResult:
        if not pattern:
            return ToolResult(success=False, error="pattern is required")
        # Python's glob does not normalize ".." segments — a crafted pattern
        # like "../../Windows/*.ini" would walk out of the sandbox. Reject
        # such patterns up front, and still enforce containment per match
        # below (defense in depth, identical rule to every other command).
        if ".." in Path(pattern).parts:
            return ToolResult(
                success=False,
                error="Search pattern is not allowed: '..' segments are prohibited",
            )
        matches = []
        truncated = False
        for base in _allowed_bases():
            base_str = str(base.resolve())
            for match in glob_module.iglob(
                f"{base_str}/**/{pattern}", recursive=True
            ):
                try:
                    # Same containment rule as every other command: resolve
                    # (follows symlinks) and require the result to stay inside
                    # an allowed base. Matches reached via symlinks, drive
                    # letters, or UNC paths are rejected here.
                    m = _check_allowed(Path(match))
                except PermissionError:
                    continue
                if m.is_file() or m.is_dir():
                    matches.append(
                        {
                            "path": str(m),
                            "type": "directory" if m.is_dir() else "file",
                            "size": m.stat().st_size if m.is_file() else None,
                        }
                    )
                    if len(matches) >= settings.max_search_results:
                        truncated = True
                        break
            if truncated:
                break
        matches.sort(key=lambda x: x["path"])
        data = {
            "pattern": pattern,
            "matches": matches,
            "count": len(matches),
        }
        if truncated:
            data["truncated"] = True
        return ToolResult(
            success=True,
            data=data,
        )

    def _rename(self, path: str, new_name: str) -> ToolResult:
        if not path or not new_name:
            return ToolResult(success=False, error="Both path and new_name are required")
        src = _resolve_path(path)
        if not src.exists():
            return ToolResult(success=False, error=f"Not found: {path}")
        dst = _resolve_path(new_name)
        # If new_name is just a name (no path separator), place it in the same directory
        if "/" not in new_name and "\\" not in new_name:
            dst = src.parent / new_name
            dst = _check_allowed(dst)
        src.rename(dst)
        return ToolResult(
            success=True,
            data={"message": f"Renamed to {dst.name}", "from": str(src), "to": str(dst)},
        )

    def _delete(self, path: str, confirmed: bool) -> ToolResult:
        if not path:
            return ToolResult(success=False, error="path is required")
        p = _resolve_path(path)
        if not p.exists():
            return ToolResult(success=False, error=f"Not found: {path}")

        if not confirmed:
            return ToolResult(
                success=True,
                data={
                    "confirmation_required": True,
                    "message": (
                        f"Are you sure you want to delete '{p.name}'? "
                        f"Call this tool again with confirmed=true to proceed."
                    ),
                },
            )

        if p.is_dir():
            try:
                p.rmdir()
            except OSError:
                return ToolResult(
                    success=False,
                    error=f"Cannot delete '{path}': directory is not empty",
                )
        else:
            p.unlink()
        return ToolResult(
            success=True,
            data={"message": f"Deleted: {p}", "path": str(p)},
        )
