# LIST_SITES Implementation Document

## Overview
Implementation of site access functionality for the Enhanced Profile page using the MXAPISITE endpoint to retrieve user site authorizations based on SQL EXISTS logic with authallsites checking.

## SQL Logic
```sql
SELECT SITEID FROM SITEAUTH s WHERE s.groupname IN (
    SELECT groupname FROM maxgroup
    WHERE EXISTS (
        SELECT 1 FROM groupuser
        WHERE userid LIKE '%USERNAME%'
        AND groupuser.groupname = maxgroup.groupname
    )
);
```

### Business Logic
1. **Check if user has ANY group with authallsites=1**
2. **If YES → Return ALL distinct sites from entire SITEAUTH table**
3. **If NO → Return only sites specific to user's groups**

## Implementation Steps

### 1. Backend API Service

#### Create SiteAccessService.js
```javascript
// services/SiteAccessService.js
import { maximoApi } from './maximoApi';

class SiteAccessService {
    constructor() {
        this.baseUrl = process.env.MAXIMO_URL;
        this.apiKey = process.env.MAXIMO_API_KEY;
    }

    /**
     * Get user site access based on SQL EXISTS logic
     * @param {string} userid - User ID to query
     * @returns {Promise<Array>} Array of site IDs user has access to
     */
    async getUserSiteAccess(userid) {
        try {
            // Step 1: Get user groups and check authallsites
            const userGroups = await this.getUserGroups(userid);
            const hasAuthAllSites = await this.checkAuthAllSites(userid, userGroups);

            if (hasAuthAllSites) {
                // Return ALL distinct sites from SITEAUTH table
                return await this.getAllSiteAuthSites();
            } else {
                // Return only sites for user's specific groups
                return await this.getUserSpecificSites(userGroups);
            }
        } catch (error) {
            console.error('Error getting user site access:', error);
            throw error;
        }
    }

    /**
     * Get user's group memberships
     */
    async getUserGroups(userid) {
        const response = await maximoApi.get('/api/os/mxapisite', {
            params: {
                'oslc.select': 'personid,maxuser{userid,groupuser{groupname}}',
                'oslc.where': `personid="${userid}"`,
                'oslc.pageSize': '1'
            }
        });

        const groups = [];
        if (response.data['rdfs:member'] && response.data['rdfs:member'].length > 0) {
            const member = response.data['rdfs:member'][0];
            if (member.maxuser) {
                for (const maxuser of member.maxuser) {
                    if (maxuser.groupuser) {
                        for (const groupuser of maxuser.groupuser) {
                            if (groupuser.groupname) {
                                groups.push(groupuser.groupname);
                            }
                        }
                    }
                }
            }
        }
        return groups;
    }

    /**
     * Check if user has authallsites=1 in any group
     */
    async checkAuthAllSites(userid, userGroups) {
        const response = await maximoApi.get('/api/os/mxapisite', {
            params: {
                'oslc.select': 'personid,maxuser{userid,groupuser{groupname,maxgroup{groupname,authallsites}}}',
                'oslc.where': `personid="${userid}"`,
                'oslc.pageSize': '1'
            }
        });

        if (response.data['rdfs:member'] && response.data['rdfs:member'].length > 0) {
            const member = response.data['rdfs:member'][0];
            if (member.maxuser) {
                for (const maxuser of member.maxuser) {
                    if (maxuser.groupuser) {
                        for (const groupuser of maxuser.groupuser) {
                            if (groupuser.maxgroup) {
                                for (const maxgroup of groupuser.maxgroup) {
                                    if (maxgroup.authallsites === true) {
                                        return true;
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        return false;
    }

    /**
     * Get ALL distinct sites from SITEAUTH table
     */
    async getAllSiteAuthSites() {
        const response = await maximoApi.get('/api/os/mxapisite', {
            params: {
                'oslc.select': 'personid,maxuser{groupuser{groupname,maxgroup{groupname,siteauth{siteid}}}}',
                'oslc.pageSize': '1000'
            }
        });

        const allSites = new Set();
        if (response.data['rdfs:member']) {
            for (const member of response.data['rdfs:member']) {
                if (member.maxuser) {
                    for (const maxuser of member.maxuser) {
                        if (maxuser.groupuser) {
                            for (const groupuser of maxuser.groupuser) {
                                if (groupuser.maxgroup) {
                                    for (const maxgroup of groupuser.maxgroup) {
                                        if (maxgroup.siteauth) {
                                            for (const siteauth of maxgroup.siteauth) {
                                                if (siteauth.siteid) {
                                                    allSites.add(siteauth.siteid);
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        return Array.from(allSites).sort();
    }

    /**
     * Get sites specific to user's groups
     */
    async getUserSpecificSites(userGroups) {
        const response = await maximoApi.get('/api/os/mxapisite', {
            params: {
                'oslc.select': 'personid,maxuser{groupuser{groupname,maxgroup{groupname,siteauth{siteid}}}}',
                'oslc.pageSize': '1000'
            }
        });

        const userSites = new Set();
        if (response.data['rdfs:member']) {
            for (const member of response.data['rdfs:member']) {
                if (member.maxuser) {
                    for (const maxuser of member.maxuser) {
                        if (maxuser.groupuser) {
                            for (const groupuser of maxuser.groupuser) {
                                const groupname = groupuser.groupname;

                                // Only process if this group belongs to our user
                                if (userGroups.includes(groupname)) {
                                    if (groupuser.maxgroup) {
                                        for (const maxgroup of groupuser.maxgroup) {
                                            if (maxgroup.siteauth) {
                                                for (const siteauth of maxgroup.siteauth) {
                                                    if (siteauth.siteid) {
                                                        userSites.add(siteauth.siteid);
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        return Array.from(userSites).sort();
    }

    /**
     * Get site details for display
     */
    async getSiteDetails(siteIds) {
        if (!siteIds || siteIds.length === 0) return [];

        // This would query site details from appropriate endpoint
        // For now, return basic structure
        return siteIds.map(siteid => ({
            siteid,
            description: `Site ${siteid}`,
            status: 'ACTIVE'
        }));
    }
}

export default new SiteAccessService();
```

### 2. Backend API Endpoint

#### Add to routes/api.js
```javascript
// routes/api.js
import SiteAccessService from '../services/SiteAccessService.js';

// Add new route for site access
router.get('/user/:userid/site-access', async (req, res) => {
    try {
        const { userid } = req.params;
        const siteAccess = await SiteAccessService.getUserSiteAccess(userid);
        const siteDetails = await SiteAccessService.getSiteDetails(siteAccess);

        res.json({
            success: true,
            data: {
                userid,
                totalSites: siteAccess.length,
                siteIds: siteAccess,
                siteDetails
            }
        });
    } catch (error) {
        console.error('Error fetching user site access:', error);
        res.status(500).json({
            success: false,
            error: 'Failed to fetch user site access'
        });
    }
});
```

### 3. Frontend Components

#### Create SiteAccessTab.jsx
```jsx
// components/SiteAccessTab.jsx
import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Loader2, MapPin, Shield, Building } from 'lucide-react';

const SiteAccessTab = ({ userId }) => {
    const [siteAccess, setSiteAccess] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        if (userId) {
            fetchSiteAccess();
        }
    }, [userId]);

    const fetchSiteAccess = async () => {
        try {
            setLoading(true);
            const response = await fetch(`/api/user/${userId}/site-access`);
            const data = await response.json();

            if (data.success) {
                setSiteAccess(data.data);
            } else {
                setError(data.error);
            }
        } catch (err) {
            setError('Failed to fetch site access data');
            console.error('Error fetching site access:', err);
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center p-8">
                <Loader2 className="h-8 w-8 animate-spin" />
                <span className="ml-2">Loading site access...</span>
            </div>
        );
    }

    if (error) {
        return (
            <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
                <p className="text-red-600">Error: {error}</p>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Summary Card */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Shield className="h-5 w-5" />
                        Site Access Summary
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div className="text-center p-4 bg-blue-50 rounded-lg">
                            <div className="text-2xl font-bold text-blue-600">
                                {siteAccess?.totalSites || 0}
                            </div>
                            <div className="text-sm text-gray-600">Total Sites</div>
                        </div>
                        <div className="text-center p-4 bg-green-50 rounded-lg">
                            <div className="text-2xl font-bold text-green-600">
                                {siteAccess?.siteIds?.length || 0}
                            </div>
                            <div className="text-sm text-gray-600">Authorized Sites</div>
                        </div>
                        <div className="text-center p-4 bg-purple-50 rounded-lg">
                            <div className="text-2xl font-bold text-purple-600">
                                {siteAccess?.userid || 'N/A'}
                            </div>
                            <div className="text-sm text-gray-600">User ID</div>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Site List */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Building className="h-5 w-5" />
                        Authorized Sites
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {siteAccess?.siteDetails?.length > 0 ? (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            {siteAccess.siteDetails.map((site) => (
                                <div
                                    key={site.siteid}
                                    className="p-4 border rounded-lg hover:shadow-md transition-shadow"
                                >
                                    <div className="flex items-center justify-between mb-2">
                                        <h3 className="font-semibold text-lg">
                                            {site.siteid}
                                        </h3>
                                        <Badge variant="outline">
                                            {site.status}
                                        </Badge>
                                    </div>
                                    <p className="text-gray-600 text-sm">
                                        {site.description}
                                    </p>
                                    <div className="flex items-center mt-2 text-xs text-gray-500">
                                        <MapPin className="h-3 w-3 mr-1" />
                                        Site Authorization
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="text-center py-8 text-gray-500">
                            <Building className="h-12 w-12 mx-auto mb-4 opacity-50" />
                            <p>No site access found for this user</p>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Raw Site IDs for Development */}
            <Card>
                <CardHeader>
                    <CardTitle>Site IDs (Development)</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="bg-gray-100 p-4 rounded-lg">
                        <code className="text-sm">
                            {siteAccess?.siteIds?.join(', ') || 'No sites'}
                        </code>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
};

export default SiteAccessTab;

### 4. Integration with Enhanced Profile

#### Update EnhancedProfile.jsx
```jsx
// Add import
import SiteAccessTab from './SiteAccessTab';

// Add to tabs array
const tabs = [
    { id: 'overview', label: 'Overview', icon: User },
    { id: 'workorders', label: 'Work Orders', icon: ClipboardList },
    { id: 'siteaccess', label: 'Site Access', icon: Shield }, // NEW TAB
    { id: 'settings', label: 'Settings', icon: Settings }
];

// Add to tab content rendering
{activeTab === 'siteaccess' && (
    <SiteAccessTab userId={selectedUser?.userid || selectedUser?.personid} />
)}
```

### 5. Database/API Configuration

#### Environment Variables (.env)
```bash
# Add to existing .env file
MAXIMO_URL=https://vectrustst01.manage.v2x.maximotest.gov2x.com/maximo
MAXIMO_API_KEY=your_api_key_here
MAXIMO_USER_CONTEXT=crawford.moore@vectrus.com
```

#### Update maximoApi.js
```javascript
// services/maximoApi.js
import axios from 'axios';

const maximoApi = axios.create({
    baseURL: process.env.MAXIMO_URL,
    headers: {
        'Accept': 'application/json',
        'apikey': process.env.MAXIMO_API_KEY,
        'x-user-context': process.env.MAXIMO_USER_CONTEXT
    },
    timeout: 30000
});

// Add request interceptor for logging
maximoApi.interceptors.request.use(
    (config) => {
        console.log(`Making request to: ${config.url}`);
        return config;
    },
    (error) => {
        return Promise.reject(error);
    }
);

// Add response interceptor for error handling
maximoApi.interceptors.response.use(
    (response) => {
        return response;
    },
    (error) => {
        console.error('Maximo API Error:', error.response?.data || error.message);
        return Promise.reject(error);
    }
);

export { maximoApi };
```

## Testing Implementation

### 1. Test Data
Based on our analysis, the following test results should be expected:

```javascript
// Test cases
const testCases = [
    {
        userid: 'MOOR382170',
        expected: 'BBOS,CJORD,DLA,IKWAJ,KDFAC,LCVIRQ,LCVKWT,LCVT,LGCAP,LGCPH,NSGBA,PBOS,QBOSS,RBOSS,THULE',
        reason: 'Has authallsites=1 in groups MAXADMIN, IMSADMINS, CORP2_USERS'
    },
    {
        userid: 'TINU.THOMAS',
        expected: 'TBD - Need to verify user exists and check authallsites',
        reason: 'User verification needed'
    }
];
```

### 2. Unit Tests
```javascript
// tests/SiteAccessService.test.js
import SiteAccessService from '../services/SiteAccessService';

describe('SiteAccessService', () => {
    test('should return all sites for user with authallsites=1', async () => {
        const result = await SiteAccessService.getUserSiteAccess('MOOR382170');
        expect(result).toContain('NSGBA');
        expect(result).toContain('BBOS');
        expect(result.length).toBeGreaterThan(10);
    });

    test('should return specific sites for user without authallsites', async () => {
        // Test with a user that doesn't have authallsites=1
        const result = await SiteAccessService.getUserSiteAccess('TEST_USER');
        expect(Array.isArray(result)).toBe(true);
    });
});
```

## Deployment Steps

### 1. Backend Deployment
1. Add `SiteAccessService.js` to services directory
2. Update API routes with new endpoint
3. Update environment variables
4. Test API endpoint: `GET /api/user/MOOR382170/site-access`

### 2. Frontend Deployment
1. Add `SiteAccessTab.jsx` component
2. Update `EnhancedProfile.jsx` with new tab
3. Add required icons (Shield, Building, MapPin)
4. Test component rendering

### 3. Integration Testing
1. Test with known user MOOR382170
2. Verify authallsites=1 logic returns all 15 sites
3. Test error handling for non-existent users
4. Verify UI displays correctly

## Expected Results

### MOOR382170 (Confirmed)
- **Groups**: MAXADMIN, MAXMOB, MAXEVERYONE, MAXDEFLTREG, IMSADMINS, CORP2_USERS
- **AuthAllSites**: True (via MAXADMIN, IMSADMINS, CORP2_USERS)
- **Result**: All 15 sites from SITEAUTH table
- **Sites**: BBOS,CJORD,DLA,IKWAJ,KDFAC,LCVIRQ,LCVKWT,LCVT,LGCAP,LGCPH,NSGBA,PBOS,QBOSS,RBOSS,THULE

### Implementation Priority
1. **High**: Backend SiteAccessService implementation
2. **High**: API endpoint creation
3. **Medium**: Frontend SiteAccessTab component
4. **Medium**: Enhanced Profile integration
5. **Low**: Advanced UI features and styling

## Files to Create/Modify

### New Files
- `services/SiteAccessService.js`
- `components/SiteAccessTab.jsx`
- `tests/SiteAccessService.test.js`

### Modified Files
- `routes/api.js` (add new endpoint)
- `components/EnhancedProfile.jsx` (add new tab)
- `services/maximoApi.js` (update configuration)
- `.env` (add environment variables)

## Success Criteria
✅ API returns correct site list for MOOR382170 (15 sites)
✅ UI displays site access tab in Enhanced Profile
✅ AuthAllSites logic works correctly
✅ Error handling for invalid users
✅ Performance acceptable for large site lists
```
