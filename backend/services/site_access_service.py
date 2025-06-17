#!/usr/bin/env python3

import os
import requests
import json
import base64
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get Maximo API details from environment variables
MAXIMO_BASE_URL = os.getenv('MAXIMO_BASE_URL')
MAXIMO_API_KEY = os.getenv('MAXIMO_API_KEY')
MAXIMO_VERIFY_SSL = os.getenv('MAXIMO_VERIFY_SSL', 'True').lower() == 'true'

# Cache for storing site access data
site_access_cache = {}
CACHE_DURATION = 300  # 5 minutes

# Dedicated cache for ALL sites (aggressive caching - 30 minutes)
all_sites_cache = None
all_sites_cache_time = None
ALL_SITES_CACHE_DURATION = 1800  # 30 minutes

class SiteAccessService:
    """
    Lightning-fast Site Access Service for retrieving user access information
    """

    @staticmethod
    def get_site_access_data(person_id):
        """
        Get comprehensive site access data for a person ID
        Returns cached data if available and fresh
        """
        cache_key = f"site_access_{person_id}"
        current_time = time.time()

        # Check cache first
        if cache_key in site_access_cache:
            cached_data, cache_time = site_access_cache[cache_key]
            if current_time - cache_time < CACHE_DURATION:
                return cached_data

        # Fetch fresh data
        try:
            data = SiteAccessService._fetch_mxapisite_data(person_id)
            if data:
                # Cache the data
                site_access_cache[cache_key] = (data, current_time)
                return data
        except Exception as e:
            pass

        return None

    @staticmethod
    def _fetch_mxapisite_data(person_id):
        """
        Fetch data from MXAPISITE endpoint for the given person ID
        """
        # Try multiple approaches to get the data
        encoded_id = base64.b64encode(person_id.encode('utf-8')).decode('utf-8')

        approaches = [
            f"{MAXIMO_BASE_URL}/api/os/mxapisite/_{encoded_id}",
            f"{MAXIMO_BASE_URL}/api/os/mxapisite/{person_id}",
        ]

        headers = {
            'Accept': 'application/json',
            'apikey': MAXIMO_API_KEY
        }

        for url in approaches:
            try:
                response = requests.get(url, headers=headers, verify=MAXIMO_VERIFY_SSL, timeout=8)
                if response.status_code == 200:
                    return response.json()
            except Exception:
                continue

        # If direct access fails, try querying the collection
        try:
            url = f"{MAXIMO_BASE_URL}/api/os/mxapisite"
            params = {
                '_compact': 'true',
                'oslc.where': f'siteid="{person_id}"',
                'oslc.pageSize': '1'
            }
            response = requests.get(url, headers=headers, params=params, verify=MAXIMO_VERIFY_SSL, timeout=8)
            if response.status_code == 200:
                data = response.json()
                members = data.get('member', []) or data.get('rdfs:member', [])
                if members:
                    return members[0]
        except Exception:
            pass

        return None

    @staticmethod
    def get_person_data(person_id):
        """
        Extract person table data with capitalized field names
        """
        data = SiteAccessService.get_site_access_data(person_id)
        if not data:
            return None

        person_fields = {
            'personid': 'Personid',
            'firstname': 'Firstname',
            'lastname': 'Lastname',
            'displayname': 'Displayname',
            'status': 'Status',
            'status_description': 'Status_description',
            'employeetype': 'Employeetype',
            'employeetype_description': 'Employeetype_description',
            'locationorg': 'Locationorg',
            'locationsite': 'Locationsite',
            'timezone': 'Timezone',
            'timezone_description': 'Timezone_description',
            'statusdate': 'Statusdate',
            'title': 'Title',
            'department': 'Department',
            'supervisor': 'Supervisor',
            'sendersysid': 'Sendersysid'
        }

        person_data = {}
        for field, display_name in person_fields.items():
            value = data.get(f'spi:{field}', 'N/A')
            person_data[display_name] = value

        return person_data

    @staticmethod
    def get_maxuser_data(person_id):
        """
        Extract maxuser table data with capitalized field names
        """
        data = SiteAccessService.get_site_access_data(person_id)
        if not data or 'spi:maxuser' not in data or not data['spi:maxuser']:
            return None

        user_data = data['spi:maxuser'][0]  # Get first user record

        maxuser_fields = {
            'userid': 'Userid',
            'loginid': 'Loginid',
            'password': 'Password',
            'status': 'Status',
            'status_description': 'Status_description',
            'type': 'Type',
            'type_description': 'Type_description',
            'defsite': 'Defsite',
            'ud_type': 'Ud_type',
            'ud_type_description': 'Ud_type_description',
            'ud_ticket': 'Ud_ticket',
            'memo': 'Memo'
        }

        maxuser_data = {}
        for field, display_name in maxuser_fields.items():
            value = user_data.get(f'spi:{field}', 'N/A')
            maxuser_data[display_name] = value

        return maxuser_data

    @staticmethod
    def get_groups_data(person_id):
        """
        Extract group memberships data (combined groupuser + maxgroup)
        """
        data = SiteAccessService.get_site_access_data(person_id)
        if not data or 'spi:maxuser' not in data or not data['spi:maxuser']:
            return []

        user_data = data['spi:maxuser'][0]
        if 'spi:groupuser' not in user_data or not user_data['spi:groupuser']:
            return []

        groups = []
        for group_data in user_data['spi:groupuser']:
            group_info = {
                'Group Name': group_data.get('spi:groupname', 'N/A'),
                'Description': 'N/A',
                'AUTHALLSITES': 'N/A'
            }

            # Get description and AUTHALLSITES from maxgroup if available
            if 'spi:maxgroup' in group_data and group_data['spi:maxgroup']:
                maxgroup = group_data['spi:maxgroup'][0]
                group_info['Description'] = maxgroup.get('spi:description', 'N/A')
                authallsites = maxgroup.get('spi:authallsites', False)
                group_info['AUTHALLSITES'] = '1' if authallsites else '0'

            groups.append(group_info)

        return groups

    @staticmethod
    def get_sites_data(person_id):
        """
        Extract site authorizations data
        Special logic: If any group has AUTHALLSITES=1, show ALL distinct sites from entire siteauth table
        """
        data = SiteAccessService.get_site_access_data(person_id)
        if not data or 'spi:maxuser' not in data or not data['spi:maxuser']:
            return []

        user_data = data['spi:maxuser'][0]
        if 'spi:groupuser' not in user_data or not user_data['spi:groupuser']:
            return []

        # Check if any group has AUTHALLSITES=1
        has_authallsites = False
        user_specific_sites = []

        for group_data in user_data['spi:groupuser']:
            if 'spi:maxgroup' in group_data and group_data['spi:maxgroup']:
                maxgroup = group_data['spi:maxgroup'][0]

                # Check AUTHALLSITES flag
                authallsites = maxgroup.get('spi:authallsites', False)
                if authallsites:
                    has_authallsites = True

                # Collect user's specific sites
                if 'spi:siteauth' in maxgroup and maxgroup['spi:siteauth']:
                    for siteauth in maxgroup['spi:siteauth']:
                        site_info = {
                            'Site ID': siteauth.get('spi:siteid', 'N/A'),
                            'Organization': siteauth.get('spi:orgid', 'N/A')
                        }
                        user_specific_sites.append(site_info)

        if has_authallsites:
            # User has AUTHALLSITES=1, try to fetch ALL sites from the entire Maximo system
            all_sites = SiteAccessService._fetch_all_sites_from_maximo()
            if all_sites:
                return all_sites
            else:
                # Fallback: if we can't get all sites, return user's specific sites
                seen_sites = set()
                distinct_sites = []
                for site in user_specific_sites:
                    site_key = site['Site ID']
                    if site_key not in seen_sites:
                        seen_sites.add(site_key)
                        distinct_sites.append(site)
                return distinct_sites
        else:
            # Return only user's specific site authorizations
            # Remove duplicates
            seen_sites = set()
            distinct_sites = []
            for site in user_specific_sites:
                site_key = site['Site ID']
                if site_key not in seen_sites:
                    seen_sites.add(site_key)
                    distinct_sites.append(site)
            return distinct_sites

    @staticmethod
    def _fetch_all_sites_from_maximo():
        """
        LIGHTNING-FAST retrieval of ALL sites in the system with aggressive caching
        NO COMPROMISE - Gets ALL sites with 30-minute cache for maximum performance
        """
        global all_sites_cache, all_sites_cache_time
        current_time = time.time()

        # Check aggressive cache first (30 minutes)
        if all_sites_cache is not None and all_sites_cache_time is not None:
            if current_time - all_sites_cache_time < ALL_SITES_CACHE_DURATION:
                return all_sites_cache

        # Cache miss - fetch ALL sites with multiple aggressive strategies
        all_sites = SiteAccessService._aggressive_fetch_all_sites()

        if all_sites:
            # Cache for 30 minutes
            all_sites_cache = all_sites
            all_sites_cache_time = current_time
            return all_sites

        # Return cached data even if expired as fallback
        if all_sites_cache is not None:
            return all_sites_cache

        return []

    @staticmethod
    def _aggressive_fetch_all_sites():
        """
        Aggressive multi-strategy approach to get ALL sites in the system
        """
        headers = {
            'Accept': 'application/json',
            'apikey': MAXIMO_API_KEY
        }

        # Strategy 1: Try direct site table access (fastest if available)
        strategies = [
            # Direct site table with active filter
            (f"{MAXIMO_BASE_URL}/api/os/site", {
                'oslc.where': 'active=1',
                'oslc.select': 'siteid,orgid',
                'oslc.pageSize': '10000'
            }),
            # Direct site table without filter
            (f"{MAXIMO_BASE_URL}/api/os/site", {
                'oslc.select': 'siteid,orgid',
                'oslc.pageSize': '10000'
            }),
            # MXAPISITE with maximum page size
            (f"{MAXIMO_BASE_URL}/api/os/mxapisite", {
                'oslc.pageSize': '10000',
                'oslc.select': 'personid,locationsite,locationorg'
            }),
            # Organization table as fallback
            (f"{MAXIMO_BASE_URL}/api/os/organization", {
                'oslc.select': 'orgid',
                'oslc.pageSize': '10000'
            })
        ]

        for url, params in strategies:
            try:
                response = requests.get(url, headers=headers, params=params, verify=MAXIMO_VERIFY_SSL, timeout=30)

                if response.status_code == 200:
                    data = response.json()
                    members = data.get('member', []) or data.get('rdfs:member', [])

                    if members:
                        sites = SiteAccessService._extract_sites_from_response(members, url)
                        if sites and len(sites) >= 15:  # Only accept if we get a reasonable number of sites
                            return sites

            except Exception:
                continue

        return []

    @staticmethod
    def _extract_sites_from_response(members, url):
        """
        Extract sites from API response based on endpoint type
        """
        all_sites = []
        seen_sites = set()

        for record in members:
            sites_from_record = []

            if 'site' in url and 'mxapi' not in url:
                # Direct site table
                site_id = (record.get('spi:siteid') or record.get('siteid'))
                org_id = (record.get('spi:orgid') or record.get('orgid'))
                if site_id:
                    sites_from_record.append((site_id, org_id or 'Unknown'))

            elif 'mxapisite' in url:
                # MXAPISITE - extract from person location data
                site_id = (record.get('spi:locationsite') or record.get('locationsite'))
                org_id = (record.get('spi:locationorg') or record.get('locationorg'))
                if site_id:
                    sites_from_record.append((site_id, org_id or 'Unknown'))

                # Also check all fields for site references
                for key, value in record.items():
                    if 'site' in key.lower() and value and value not in ['N/A', 'Unknown']:
                        sites_from_record.append((value, org_id or 'Unknown'))

            elif 'organization' in url:
                # Organization table - use orgid as both site and org
                org_id = (record.get('spi:orgid') or record.get('orgid'))
                if org_id:
                    sites_from_record.append((org_id, org_id))

            # Add unique sites
            for site_id, org_id in sites_from_record:
                if site_id and site_id not in seen_sites:
                    seen_sites.add(site_id)
                    all_sites.append({
                        'Site ID': site_id,
                        'Organization': org_id
                    })

        return sorted(all_sites, key=lambda x: x['Site ID']) if all_sites else []

    @staticmethod
    def clear_cache():
        """
        Clear all caches (site access + all sites)
        """
        global site_access_cache, all_sites_cache, all_sites_cache_time
        site_access_cache.clear()
        all_sites_cache = None
        all_sites_cache_time = None

    @staticmethod
    def get_cache_stats():
        """
        Get cache statistics
        """
        global all_sites_cache, all_sites_cache_time
        current_time = time.time()

        all_sites_cached = all_sites_cache is not None
        all_sites_fresh = False
        all_sites_count = 0

        if all_sites_cached and all_sites_cache_time is not None:
            all_sites_fresh = (current_time - all_sites_cache_time) < ALL_SITES_CACHE_DURATION
            all_sites_count = len(all_sites_cache) if all_sites_cache else 0

        return {
            'cached_entries': len(site_access_cache),
            'cache_duration': CACHE_DURATION,
            'all_sites_cached': all_sites_cached,
            'all_sites_fresh': all_sites_fresh,
            'all_sites_count': all_sites_count,
            'all_sites_cache_duration': ALL_SITES_CACHE_DURATION
        }
