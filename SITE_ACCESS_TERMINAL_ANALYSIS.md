# Site Access Terminal Analysis Documentation

## Overview
This document explains how the successful terminal site access analysis was achieved that produced the following output:

```
Site Access Analysis for MOOR382170:
🎯 OVERALL ACCESS LEVEL: ALL_SITES
👥 USER GROUPS (6):
CORP2_USERS ⭐ (authallsites=1)
IMSADMINS ⭐ (authallsites=1)
MAXADMIN ⭐ (authallsites=1)
MAXDEFLTREG
MAXEVERYONE
MAXMOB
🌐 AUTHALLSITES GROUPS (3):
CORP2_USERS
IMSADMINS
MAXADMIN
✅ USER HAS 'ALL SITES' ACCESS through 3 group(s)
```

## The Working Script

```python
#!/usr/bin/env python3
"""
Site Access Analysis Script
Queries MXAPISITE endpoint to analyze user site access through group relationships
"""

import requests
import json
from typing import Dict, List, Tuple, Any

class SiteAccessAnalyzer:
    def __init__(self, base_url: str, session: requests.Session):
        self.base_url = base_url
        self.session = session
    
    def analyze_user_site_access(self, userid: str) -> Dict[str, Any]:
        """
        Analyze site access for a user by querying MXAPISITE endpoint
        
        The key insight: MXAPISITE contains the complete relationship chain:
        person -> maxuser -> groupuser -> maxgroup -> siteauth
        """
        
        # Step 1: Get user's groups and authallsites status
        has_authallsites, user_groups, authallsites_groups = self._check_authallsites(userid)
        
        # Step 2: Get specific sites (if limited access)
        if has_authallsites:
            sites = self._get_all_sites()  # User has access to ALL sites
            access_level = "ALL_SITES"
        else:
            sites = self._get_user_specific_sites(userid)
            access_level = "LIMITED_SITES"
        
        return {
            'userid': userid,
            'access_level': access_level,
            'has_authallsites': has_authallsites,
            'user_groups': user_groups,
            'authallsites_groups': authallsites_groups,
            'sites': sites,
            'total_sites': len(sites)
        }
    
    def _check_authallsites(self, userid: str) -> Tuple[bool, List[str], List[str]]:
        """
        Check if user has authallsites=1 in ANY group
        
        Query: Get user's groups and check authallsites flag
        """
        endpoint = f"{self.base_url}/api/os/mxapisite"
        
        params = {
            'oslc.select': 'personid,maxuser{userid,groupuser{groupname,maxgroup{groupname,authallsites}}}',
            'oslc.where': f'personid="{userid}"',
            'oslc.pageSize': '100'
        }
        
        response = self.session.get(endpoint, params=params)
        data = response.json()
        
        user_groups = []
        authallsites_groups = []
        
        # Parse the nested structure
        for member in data.get('rdfs:member', []):
            maxuser_list = member.get('maxuser', [])
            for maxuser in maxuser_list:
                groupuser_list = maxuser.get('groupuser', [])
                for groupuser in groupuser_list:
                    group_name = groupuser.get('groupname')
                    if group_name:
                        user_groups.append(group_name)
                        
                        # Check if this group has authallsites=1
                        maxgroup_list = groupuser.get('maxgroup', [])
                        for maxgroup in maxgroup_list:
                            if maxgroup.get('authallsites') == 1:
                                authallsites_groups.append(group_name)
        
        has_authallsites = len(authallsites_groups) > 0
        
        return has_authallsites, list(set(user_groups)), list(set(authallsites_groups))
    
    def _get_user_specific_sites(self, userid: str) -> List[str]:
        """
        Get specific sites user has access to through siteauth table
        """
        endpoint = f"{self.base_url}/api/os/mxapisite"
        
        params = {
            'oslc.select': 'personid,maxuser{userid,groupuser{groupname,maxgroup{siteauth{siteid,site}}}}',
            'oslc.where': f'personid="{userid}"',
            'oslc.pageSize': '1000'
        }
        
        response = self.session.get(endpoint, params=params)
        data = response.json()
        
        sites = set()
        
        # Parse nested structure to extract sites
        for member in data.get('rdfs:member', []):
            maxuser_list = member.get('maxuser', [])
            for maxuser in maxuser_list:
                groupuser_list = maxuser.get('groupuser', [])
                for groupuser in groupuser_list:
                    maxgroup_list = groupuser.get('maxgroup', [])
                    for maxgroup in maxgroup_list:
                        siteauth_list = maxgroup.get('siteauth', [])
                        for siteauth in siteauth_list:
                            siteid = siteauth.get('siteid') or siteauth.get('site')
                            if siteid:
                                sites.add(siteid)
        
        return sorted(list(sites))

    def _get_all_sites(self) -> List[str]:
        """
        Get all distinct sites from the system (for authallsites=1 users)
        """
        endpoint = f"{self.base_url}/api/os/mxapisite"
        
        params = {
            'oslc.select': 'personid,maxuser{groupuser{maxgroup{siteauth{siteid,site}}}}',
            'oslc.pageSize': '10000'
        }
        
        response = self.session.get(endpoint, params=params)
        data = response.json()
        
        all_sites = set()
        
        for member in data.get('rdfs:member', []):
            maxuser_list = member.get('maxuser', [])
            for maxuser in maxuser_list:
                groupuser_list = maxuser.get('groupuser', [])
                for groupuser in groupuser_list:
                    maxgroup_list = groupuser.get('maxgroup', [])
                    for maxgroup in maxgroup_list:
                        siteauth_list = maxgroup.get('siteauth', [])
                        for siteauth in siteauth_list:
                            siteid = siteauth.get('siteid') or siteauth.get('site')
                            if siteid:
                                all_sites.add(siteid)
        
        return sorted(list(all_sites))

# Usage Functions
def print_analysis(result):
    """Print the formatted analysis"""
    userid = result['userid']
    access_level = result['access_level']
    user_groups = result['user_groups']
    authallsites_groups = result['authallsites_groups']
    
    print(f"\nSite Access Analysis for {userid}:")
    print(f"🎯 OVERALL ACCESS LEVEL: {access_level}")
    print(f"👥 USER GROUPS ({len(user_groups)}):")
    
    for group in user_groups:
        if group in authallsites_groups:
            print(f"{group} ⭐ (authallsites=1)")
        else:
            print(f"{group}")
    
    print(f"🌐 AUTHALLSITES GROUPS ({len(authallsites_groups)}):")
    for group in authallsites_groups:
        print(f"{group}")
    
    if result['has_authallsites']:
        print(f"✅ USER HAS 'ALL SITES' ACCESS through {len(authallsites_groups)} group(s)")
        print(f"This means that user {userid} has unrestricted access to ALL sites in the system because they belong to {len(authallsites_groups)} groups ({', '.join(authallsites_groups)}) that have authallsites=1 (true).")
    else:
        print(f"⚠️ USER HAS LIMITED ACCESS to {result['total_sites']} specific sites")
        print(f"Sites: {', '.join(result['sites'])}")

def main():
    """Main function to run the analysis"""
    # Import your existing token manager
    from backend.services.token_manager import token_manager
    
    # Initialize analyzer
    base_url = token_manager.base_url
    session = token_manager.session
    analyzer = SiteAccessAnalyzer(base_url, session)
    
    # Analyze users
    users = ['tinu.thomas', 'MOOR382170']
    
    results = []
    for userid in users:
        result = analyzer.analyze_user_site_access(userid)
        results.append(result)
        print_analysis(result)
    
    # Print comparison
    print("\nComparison Summary:")
    print("User\tAccess Level\tGroups with authallsites=1\tSpecific Sites")
    for result in results:
        userid = result['userid']
        access_level = result['access_level']
        authallsites_count = len(result['authallsites_groups'])
        
        if result['has_authallsites']:
            sites_info = "Access to ALL sites"
            groups_info = f"{authallsites_count} ({', '.join(result['authallsites_groups'])})"
        else:
            sites_info = f"{result['total_sites']} sites ({', '.join(result['sites'])})"
            groups_info = "0"
        
        print(f"{userid}\t{access_level}\t{groups_info}\t{sites_info}")

if __name__ == "__main__":
    main()
```

## Key Technical Details

### MXAPISITE Endpoint Structure
```
MXAPISITE
├── personid (user identifier)
└── maxuser[]
    ├── userid
    └── groupuser[]
        ├── groupname
        └── maxgroup[]
            ├── groupname
            ├── authallsites (1=true, 0=false)
            └── siteauth[]
                ├── siteid
                └── site
```

### Critical Query Parameters

**For Groups + AuthAllSites Check:**
```
oslc.select=personid,maxuser{userid,groupuser{groupname,maxgroup{groupname,authallsites}}}
oslc.where=personid="MOOR382170"
```

**For Specific Sites:**
```
oslc.select=personid,maxuser{userid,groupuser{groupname,maxgroup{siteauth{siteid,site}}}}
oslc.where=personid="MOOR382170"
```

### How to Run

1. Save this script as `site_access_analyzer.py`
2. Run from your project directory:
```bash
cd /Users/arkprabha/Desktop/Enhanced_siteidList
python3 site_access_analyzer.py
```

### Why This Worked

1. **Direct API Access**: Used direct HTTP requests to MXAPISITE endpoint
2. **Proper Session Management**: Leveraged existing authenticated session
3. **Correct Data Parsing**: Handled nested JSON structure properly
4. **Complete Relationship Chain**: Followed person->maxuser->groupuser->maxgroup->siteauth path

This approach successfully queried the MXAPISITE endpoint and retrieved site access information from the siteauth table through maxgroup relationships, exactly as required.
