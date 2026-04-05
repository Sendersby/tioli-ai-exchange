"""Executor tools — available to all Arch Agents for autonomous action.

These tools give agents the ability to DO, not just advise.
"""

EXECUTOR_TOOLS = [
    {
        "name": "execute_command",
        "description": "Run a shell command on the server. Use for: git operations, file management, service checks, package installs. All commands are logged.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
                "timeout": {"type": "integer", "default": 60},
            },
            "required": ["command"],
        },
    },
    {
        "name": "write_file",
        "description": "Write a file to the server. Use for: creating config files, writing code, generating documents, saving content. Path must be under /home/tioli/app/.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Full file path under /home/tioli/app/"},
                "content": {"type": "string", "description": "File content"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "read_file",
        "description": "Read a file from the server. Use for: reviewing code, checking configs, reading documents.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "browse_website",
        "description": "Navigate to a URL using Playwright browser, extract page content and optionally take a screenshot. Use for: competitive research, checking platform pages, monitoring.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "screenshot": {"type": "boolean", "default": True},
            },
            "required": ["url"],
        },
    },
    {
        "name": "post_social_content",
        "description": "Create and queue a social media post for a specific platform. Content is generated and queued for posting.",
        "input_schema": {
            "type": "object",
            "properties": {
                "platform": {"type": "string", "enum": ["linkedin", "twitter", "reddit", "github", "threads"]},
                "content": {"type": "string", "description": "Post content"},
                "title": {"type": "string", "description": "Title (for Reddit/LinkedIn articles)"},
            },
            "required": ["platform", "content"],
        },
    },
    {
        "name": "generate_content",
        "description": "Use Claude to generate content — social posts, legal documents, technical docs, marketing copy. Specify the type and any voice/tone requirements.",
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "What to generate"},
                "voice": {"type": "string", "description": "Optional tone/voice instructions"},
                "max_tokens": {"type": "integer", "default": 1000},
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "research_competitor",
        "description": "Browse a competitor website and generate competitive intelligence analysis.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Competitor URL to research"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "execute_task_plan",
        "description": "Execute a multi-step task plan autonomously. Provide a list of actions to perform in sequence.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tasks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "action": {"type": "string"},
                            "params": {"type": "object"},
                        },
                    },
                    "description": "List of tasks: [{action: 'write_file', params: {path: '...', content: '...'}}, ...]",
                },
            },
            "required": ["tasks"],
        },
    },
    {
        "name": "make_api_call",
        "description": "Make an HTTP request to a whitelisted external API (Stripe, LinkedIn, GitHub, etc.).",
        "input_schema": {
            "type": "object",
            "properties": {
                "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE"]},
                "url": {"type": "string"},
                "headers": {"type": "object"},
                "body": {"type": "object"},
            },
            "required": ["method", "url"],
        },
    },
]
