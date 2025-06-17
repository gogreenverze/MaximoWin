"""
Sites module for Maximo OAuth.
"""
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('token_sites')

class MaximoSitesManager:
    """Handles site operations with Maximo OAuth."""

    # Class variable to cache sites
    _sites_cache = None
    _sites_cache_timestamp = 0

    def get_available_sites(self, use_mock=False, use_cache=True, force_refresh=False):
        """Get the list of sites available to the user.

        Args:
            use_mock (bool): Parameter kept for compatibility but not used.
                             All data comes from live Maximo API.
            use_cache (bool): Whether to use cached sites if available.
            force_refresh (bool): Whether to force a refresh of the cache.

        Returns:
            list: List of site dictionaries with 'siteid' and 'description'.
        """
        import time

        # Check if we have cached sites and they're not too old (5 minutes)
        cache_valid = (
            MaximoSitesManager._sites_cache is not None and
            time.time() - MaximoSitesManager._sites_cache_timestamp < 300
        )

        # Return cached sites if valid and not forcing refresh
        if use_cache and cache_valid and not force_refresh:
            logger.info(f"Using cached sites ({len(MaximoSitesManager._sites_cache)} sites)")
            return MaximoSitesManager._sites_cache

        # Start with an empty list
        sites = []
        unique_sites = {}

        # Get user profile - this is the most reliable source of site information
        profile = self.get_user_profile(False)  # Always use live API data

        # Extract sites from profile if available
        if profile:
            # 1. First check for sites array in profile
            if 'sites' in profile and profile['sites']:
                logger.info(f"Found {len(profile['sites'])} sites in user profile")
                for site in profile['sites']:
                    siteid = site.get('siteid')
                    if siteid and siteid not in unique_sites:
                        unique_sites[siteid] = site

            # 2. Always add default site and insert site from profile
            default_site = profile.get('defaultSite') or profile.get('spi:defaultSite')
            insert_site = profile.get('spi:insertSite')

            if default_site and default_site not in unique_sites:
                unique_sites[default_site] = {
                    'siteid': default_site,
                    'description': profile.get('defaultSiteDescription', default_site)
                }

            if insert_site and insert_site not in unique_sites:
                unique_sites[insert_site] = {
                    'siteid': insert_site,
                    'description': insert_site
                }

            # 3. Check for siteauth in profile
            if 'siteauth' in profile:
                for site in profile['siteauth']:
                    siteid = site.get('site')
                    if siteid and siteid not in unique_sites:
                        unique_sites[siteid] = {
                            'siteid': siteid,
                            'description': site.get('description', siteid)
                        }

        # If we have at least 2 sites, we can skip the API calls
        if len(unique_sites) >= 2:
            logger.info(f"Using {len(unique_sites)} sites from profile")
            result = list(unique_sites.values())

            # Cache the result
            MaximoSitesManager._sites_cache = result
            MaximoSitesManager._sites_cache_timestamp = time.time()

            return result

        # If we don't have enough sites and we're logged in, try the most reliable API endpoint
        if self.is_logged_in() and len(unique_sites) < 2:
            try:
                # Only try the most reliable endpoint based on logs
                sites_url = f"{self.base_url}/oslc/sites"
                logger.info(f"Fetching available sites from {sites_url}")

                try:
                    response = self.session.get(
                        sites_url,
                        timeout=(3.05, 10),  # Reduced timeout
                        headers={"Accept": "application/json"},
                        allow_redirects=True
                    )

                    # Check for successful response
                    if response.status_code == 200:
                        # Try to parse JSON response
                        sites_data = response.json()

                        # Handle different response formats
                        if 'member' in sites_data:
                            # Format sites data to match expected format
                            for site in sites_data['member']:
                                siteid = site.get('siteid', '')
                                if siteid and siteid not in unique_sites:
                                    unique_sites[siteid] = {
                                        'siteid': siteid,
                                        'description': site.get('description', siteid)
                                    }
                            logger.info(f"Successfully fetched sites from API")
                except Exception as e:
                    logger.warning(f"Error fetching sites from API: {e}")
            except Exception as e:
                logger.error(f"Error in site fetching process: {e}")

        # If we still have no sites, log a warning but don't add mock data
        if not unique_sites:
            logger.warning("No sites found from Maximo API. Returning empty list as per strict directive to not use mock data.")

        # Convert back to list and sort by siteid
        result = list(unique_sites.values())
        result.sort(key=lambda x: x.get('siteid', ''))

        # Cache the result
        MaximoSitesManager._sites_cache = result
        MaximoSitesManager._sites_cache_timestamp = time.time()

        logger.info(f"Returning {len(result)} unique sites")
        return result
