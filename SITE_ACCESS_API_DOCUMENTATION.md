# Site Access API Documentation

## Overview
The Site Access API provides comprehensive access to user site authorization data from Maximo, including person information, user accounts, group memberships, and site authorizations with intelligent AUTHALLSITES logic.

## Base URL
```
http://127.0.0.1:5008/api/site-access
```

## Authentication
All endpoints require valid Maximo authentication via session cookies.

---

## Endpoints

### 1. Get Person Data
Retrieve person table information with capitalized field names.

**Endpoint:** `GET /api/site-access/{personid}/person`

**Parameters:**
- `personid` (string, required): The person ID to retrieve data for

**Response:**
```json
{
  "success": true,
  "data": {
    "Personid": "{personid}",
    "Firstname": "Tinu",
    "Lastname": "Thomas",
    "Displayname": "Tinu Thomas",
    "Status": "ACTIVE",
    "Status_description": "Active",
    "Employeetype": "E",
    "Employeetype_description": "Employee",
    "Locationorg": "USNAVY",
    "Locationsite": "NSGBA",
    "Timezone": "US/Eastern",
    "Timezone_description": "US/Eastern",
    "Statusdate": "2023-01-15T00:00:00+00:00",
    "Title": "IT Specialist",
    "Department": "Information Technology",
    "Supervisor": "JOHN.DOE",
    "Sendersysid": "MAXIMO"
  }
}
```

**Error Response:**
```json
{
  "success": false,
  "error": "Person not found or access denied"
}
```

---

### 2. Get MaxUser Data
Retrieve maxuser table information with capitalized field names.

**Endpoint:** `GET /api/site-access/{personid}/maxuser`

**Parameters:**
- `personid` (string, required): The person ID to retrieve data for

**Response:**
```json
{
  "success": true,
  "data": {
    "Userid": "{personid}",
    "Loginid": "tinu.thomas@vectrus.com",
    "Password": "********",
    "Status": "ACTIVE",
    "Status_description": "Active",
    "Type": "MAXUSER",
    "Type_description": "Maximo User",
    "Defsite": "NSGBA",
    "Ud_type": "EMPLOYEE",
    "Ud_type_description": "Employee",
    "Ud_ticket": "N",
    "Memo": "Standard user account"
  }
}
```

---

### 3. Get Group Memberships
Retrieve group memberships with AUTHALLSITES information.

**Endpoint:** `GET /api/site-access/{personid}/groups`

**Parameters:**
- `personid` (string, required): The person ID to retrieve data for

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "Group Name": "MAXADMIN",
      "Description": "Maximo Administrators",
      "AUTHALLSITES": "1"
    },
    {
      "Group Name": "MAXEVERYONE",
      "Description": "All Maximo Users",
      "AUTHALLSITES": "0"
    }
  ]
}
```

**AUTHALLSITES Values:**
- `"1"`: User has access to ALL sites in the system
- `"0"`: User has access only to specifically authorized sites

---

### 4. Get Site Authorizations
Retrieve site authorizations with intelligent AUTHALLSITES logic.

**Endpoint:** `GET /api/site-access/{personid}/sites`

**Parameters:**
- `personid` (string, required): The person ID to retrieve data for

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "Site ID": "NSGBA",
      "Organization": "USNAVY"
    },
    {
      "Site ID": "LCVKWT",
      "Organization": "USARMY"
    },
    {
      "Site ID": "IKWAJ",
      "Organization": "USARMY"
    }
  ]
}
```

**AUTHALLSITES Logic:**
- **If user has AUTHALLSITES=1**: Returns ALL distinct sites from the entire Maximo system
- **If user has AUTHALLSITES=0**: Returns only user's specific site authorizations

---

### 5. Clear Cache
Clear the site access cache for fresh data retrieval.

**Endpoint:** `POST /api/site-access/cache/clear`

**Response:**
```json
{
  "success": true,
  "message": "Site access cache cleared successfully"
}
```

---

### 6. Get Cache Statistics
Retrieve cache performance statistics.

**Endpoint:** `GET /api/site-access/cache/stats`

**Response:**
```json
{
  "success": true,
  "data": {
    "cached_entries": 5,
    "cache_duration": 300
  }
}
```

---

## Performance Features

### Intelligent Caching
- **Cache Duration**: 5 minutes (300 seconds)
- **Cache Key**: `site_access_{personid}`
- **Benefits**: Lightning-fast subsequent requests for the same user

### Optimized Timeouts
- **Connection Timeout**: 3.05 seconds
- **Read Timeout**: 8 seconds
- **Total Request Timeout**: 15 seconds for all sites query

### AUTHALLSITES Optimization
- **Page Size**: 1000 records for maximum site coverage
- **Distinct Sites**: Automatic deduplication of site records
- **Fallback Logic**: Returns user-specific sites if all-sites query fails

---

## Error Handling

### Common Error Responses

**Authentication Error:**
```json
{
  "success": false,
  "error": "Authentication required"
}
```

**User Not Found:**
```json
{
  "success": false,
  "error": "Person not found or access denied"
}
```

**Server Error:**
```json
{
  "success": false,
  "error": "Internal server error"
}
```

---

## Usage Examples

### JavaScript/Fetch
```javascript
// Get person data
fetch('/api/site-access/{personid}/person')
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      console.log('Person data:', data.data);
    }
  });

// Get sites with AUTHALLSITES logic
fetch('/api/site-access/{personid}/sites')
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      console.log(`Found ${data.data.length} sites`);
      data.data.forEach(site => {
        console.log(`${site['Site ID']} (${site['Organization']})`);
      });
    }
  });
```

### cURL
```bash
# Get group memberships
curl -X GET "http://127.0.0.1:5008/api/site-access/{personid}/groups" \
  -H "Accept: application/json" \
  --cookie-jar cookies.txt

# Clear cache
curl -X POST "http://127.0.0.1:5008/api/site-access/cache/clear" \
  -H "Accept: application/json" \
  --cookie-jar cookies.txt
```

---

## Integration Notes

### Enhanced Profile Page
The Site Access API is integrated into the Enhanced Profile page (`/enhanced-profile`) with:
- **4-tab interface**: Person | User Account | Group Memberships | Site Authorizations
- **Dynamic loading**: Data loads on-demand when tabs are clicked
- **Mobile-responsive**: Optimized for mobile devices
- **Visual indicators**: Green "YES (All Sites)" for AUTHALLSITES=1 users

### Performance Monitoring
- Cache hit rates and response times are tracked
- Performance statistics available via `/cache/stats` endpoint
- Automatic fallback mechanisms for reliability

---

## Version Information
- **API Version**: 1.0
- **Last Updated**: 2025-05-27
- **Compatibility**: Maximo 7.6+ with REST API support
