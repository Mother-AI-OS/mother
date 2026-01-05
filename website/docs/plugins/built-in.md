---
sidebar_position: 1
---

# Built-in Plugins

Mother AI OS includes three powerful built-in plugins.

## filesystem

File and directory operations.

| Capability | Description |
|------------|-------------|
| `read_file` | Read file contents |
| `write_file` | Write content to file |
| `append_file` | Append to file |
| `list_directory` | List directory contents |
| `file_info` | Get file metadata |
| `delete_file` | Delete a file (requires confirmation) |
| `copy_file` | Copy a file |
| `move_file` | Move/rename a file |
| `create_directory` | Create a directory |
| `exists` | Check if path exists |

## shell

Safe command execution.

| Capability | Description |
|------------|-------------|
| `run_command` | Execute a shell command (requires confirmation) |
| `run_script` | Execute a script file |
| `get_env` | Get environment variable |
| `list_env` | List environment variables |
| `which` | Find executable path |
| `get_cwd` | Get current directory |
| `hostname` | Get system hostname |
| `whoami` | Get current user |
| `command_exists` | Check if command exists |
| `system_info` | Get system information |

## web

HTTP operations.

| Capability | Description |
|------------|-------------|
| `fetch` | Generic HTTP request |
| `get` | HTTP GET request |
| `post` | HTTP POST request |
| `head` | HTTP HEAD request |
| `download` | Download file from URL |
| `check_url` | Check if URL is accessible |
| `get_json` | Fetch and parse JSON |
| `extract_links` | Extract links from HTML |
| `parse_url` | Parse URL components |
| `encode_url` | URL encode a string |
