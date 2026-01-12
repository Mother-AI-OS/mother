---
sidebar_position: 1
---

# Built-in Plugins

Mother AI OS includes 14 powerful built-in plugins with 116+ capabilities.

## Core Plugins

### filesystem

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

### shell

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

### web

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

### email

Email operations via IMAP/SMTP.

| Capability | Description |
|------------|-------------|
| `send` | Send an email |
| `list` | List emails in folder |
| `read` | Read email content |
| `search` | Search emails |
| `delete` | Delete email (requires confirmation) |
| `move` | Move email to folder |
| `list_folders` | List mailbox folders |
| `mark_read` | Mark email as read |
| `mark_unread` | Mark email as unread |
| `list_accounts` | List configured accounts |

### pdf

PDF manipulation.

| Capability | Description |
|------------|-------------|
| `merge` | Merge multiple PDFs |
| `split` | Split PDF by pages |
| `extract_text` | Extract text from PDF |
| `extract_pages` | Extract specific pages |
| `rotate` | Rotate PDF pages |
| `compress` | Compress PDF file |
| `info` | Get PDF metadata |

### tasks

Task and todo management.

| Capability | Description |
|------------|-------------|
| `add` | Add a new task |
| `list` | List all tasks |
| `complete` | Mark task complete |
| `delete` | Delete a task |
| `prioritize` | Set task priority |
| `search` | Search tasks |
| `due_today` | List tasks due today |
| `overdue` | List overdue tasks |
| `add_subtask` | Add subtask |
| `set_due_date` | Set task due date |
| `add_note` | Add note to task |

### datacraft

Document parsing and data extraction.

| Capability | Description |
|------------|-------------|
| `parse` | Parse document (PDF, DOCX, etc.) |
| `extract_tables` | Extract tables from document |
| `search` | Search document content |
| `summarize` | Generate document summary |
| `extract_entities` | Extract named entities |
| `compare` | Compare two documents |
| `convert` | Convert between formats |
| `ocr` | OCR image/scanned PDF |

## Communication Plugins

### transmit

Document transmission via multiple channels.

| Capability | Description |
|------------|-------------|
| `send_email` | Send document via email |
| `send_fax` | Send document via fax |
| `send_post` | Send via postal mail |
| `send_bea` | Send via beA (German legal) |
| `track` | Track transmission status |
| `list_channels` | List available channels |
| `validate_address` | Validate recipient address |
| `get_receipt` | Get delivery receipt |

## Privacy & Anonymity Plugins

### tor

Anonymous browsing and darknet access through Tor network.

| Capability | Description |
|------------|-------------|
| `tor_check_status` | Check Tor service status and exit node IP |
| `tor_fetch` | Fetch URLs through Tor proxy (supports .onion) |
| `tor_browse` | Browse sites with text-based browser via Tor |
| `tor_new_identity` | Request new Tor circuit/identity |
| `tor_start` | Start Tor service |
| `tor_stop` | Stop Tor service |
| `tor_search` | Search DuckDuckGo anonymously via Tor |
| `tor_whois_onion` | Get info about .onion addresses |
| `tor_list_bookmarks` | Manage darknet bookmarks |
| `tor_dns_lookup` | DNS resolution via Tor |

:::note Requirements
Requires Tor service installed and running on localhost:9050.
:::

### tor-shell

Shell command wrappers for Tor network operations.

| Capability | Description |
|------------|-------------|
| `tor_curl` | curl through Tor SOCKS proxy |
| `tor_wget` | wget with torsocks |
| `tor_nmap` | Network scanning via Tor |
| `tor_ssh` | SSH connections through Tor |
| `tor_nc` | Netcat through Tor |
| `tor_traceroute` | Traceroute via Tor |
| `tor_ping` | Ping through Tor |
| `tor_dig` | DNS queries through Tor |

## Optional Plugins

These plugins are included but may require additional configuration.

### taxlord

German tax and document management.

| Capability | Description |
|------------|-------------|
| `upload` | Upload tax document |
| `categorize` | Categorize document |
| `search` | Search tax documents |
| `export` | Export for tax software |
| `validate` | Validate document format |

### leads

German tender and lead discovery.

| Capability | Description |
|------------|-------------|
| `search` | Search for tenders |
| `subscribe` | Subscribe to alerts |
| `export` | Export lead data |
| `analyze` | Analyze tender requirements |
| `track` | Track tender status |

### google-docs

Google Docs template management.

| Capability | Description |
|------------|-------------|
| `list_templates` | List available templates |
| `create_from_template` | Create document from template |
| `fill_template` | Fill template placeholders |
| `export` | Export to PDF/DOCX |

## Plugin Summary

| Plugin | Capabilities | Category |
|--------|-------------|----------|
| filesystem | 10 | Core |
| shell | 10 | Core |
| web | 10 | Core |
| email | 10 | Core |
| pdf | 7 | Core |
| tasks | 11 | Core |
| datacraft | 8 | Core |
| transmit | 8 | Communication |
| tor | 10 | Privacy |
| tor-shell | 8 | Privacy |
| taxlord | 10 | Optional |
| leads | 5 | Optional |
| google-docs | 4 | Optional |
| demo | 5 | Example |

**Total: 116 capabilities across 14 plugins**
