"""
Token Manager for Maximo OAuth.
This is the main module that combines all the functionality from the other modules.
"""
import logging
from token_auth import MaximoAuthManager
from token_login import MaximoLoginManager
from token_api import MaximoApiManager
from token_sites import MaximoSitesManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('token_manager')

class MaximoTokenManager(MaximoAuthManager, MaximoLoginManager, MaximoApiManager, MaximoSitesManager):
    """Manages authentication tokens for Maximo OAuth.
    
    This class handles:
    - Authentication with Maximo OAuth
    - Token management (refresh, caching, etc.)
    - API calls to Maximo
    - Site management
    """
    
    def __init__(self, base_url, client_id="MAXIMO", cache_dir=None):
        """Initialize the token manager.
        
        Args:
            base_url (str): The base URL of the Maximo instance.
            client_id (str): The client ID for OAuth authentication.
            cache_dir (str): Directory to cache tokens. If None, uses ~/.maximo_oauth.
        """
        # Initialize the parent classes
        MaximoAuthManager.__init__(self, base_url, client_id, cache_dir)
