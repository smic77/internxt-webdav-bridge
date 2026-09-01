#!/usr/bin/env python3
"""
Standalone launcher for asgi-webdav with Internxt provider support
"""
import sys
import logging
from logging import getLogger

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = getLogger(__name__)

# Import asgi-webdav modules
from asgi_webdav.web_dav import WebDAV, _HTTP_PROVIDERS
from asgi_webdav.config import Config, generate_config_from_file
from asgi_webdav.server import DAVApp, get_asgi_app, AppEntryParameters

# Import our Internxt provider
from internxt_provider import InternxtProvider

# Monkey-patch the provider matching to support internxt:// URIs
original_match_provider_class = WebDAV.match_provider_class

@staticmethod
def patched_match_provider_class(p_config):
    """Patched version that supports internxt:// URIs"""
    if p_config.uri.startswith("internxt://"):
        return InternxtProvider
    
    # Fall back to original implementation
    return original_match_provider_class(p_config)

WebDAV.match_provider_class = patched_match_provider_class

# Also register in _HTTP_PROVIDERS for http/https URIs with type="internxt"
_HTTP_PROVIDERS["internxt"] = InternxtProvider

def main():
    """Main entry point"""
    logger.info("Starting ASGI WebDAV with Internxt provider support")
    
    # Generate webdav.toml dynamically from environment variables
    import os
    username = os.environ.get("WEBDAV_USERNAME", "admin")
    password = os.environ.get("WEBDAV_PASSWORD", "changeme")
    
    config_content = f"""# ASGI WebDAV configuration for Internxt (auto-generated)

[[account_mapping]]
username = "{username}"
password = "{password}"
permissions = ["+"]

[[provider_mapping]]
prefix = "/"
uri = "internxt://"
"""
    
    # Write temporary config file
    config_file = "/tmp/webdav.toml"
    with open(config_file, "w") as f:
        f.write(config_content)
    
    logger.info(f"Generated config for user: {username}")
    
    # Create AppEntryParameters
    aep = AppEntryParameters(
        bind_host="0.0.0.0",
        bind_port=8000,
        config_file=config_file
    )
    
    # Get ASGI app
    app = get_asgi_app(aep)
    
    # Run with uvicorn
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()
