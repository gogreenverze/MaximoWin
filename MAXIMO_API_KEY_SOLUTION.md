# Maximo Work Order Status Change - API Key Solution

## 🔍 Root Cause Analysis

After extensive testing with curl and analyzing the Maximo REST API documentation, we discovered the root cause of the status change failures:

### The Problem
- **Session cookies work for web interface** but **NOT for REST API endpoints**
- **All API calls were getting 302 redirects** to the login page
- **The server uses Application Server Security** which requires different authentication for API calls

### The Evidence
```bash
# All curl tests with session cookies resulted in:
< HTTP/2 302 
< location: https://auth.v2x.maximotest.gov2x.com/oidc/endpoint/MaximoAppSuite/authorize...
```

## 🔧 The Solution: API Key Authentication

Based on IBM Maximo documentation, the correct approach is:

1. **Create API Key** through Maximo web interface
2. **Use `/api/` route** instead of `/oslc/` to bypass application server security
3. **Include API key** in headers or query parameters

## 📋 Step-by-Step Implementation

### Step 1: Create API Key (Manual Process)

**You need to create an API key through the Maximo web interface:**

1. **Login to Maximo** with administrator privileges
2. **Go to Work Centers** → **Administration**
3. **Click Integration tab** → **API Key subtab**
4. **Click "Add API Key"** button
5. **Select user**: `tinu.thomas@vectrus.com`
6. **Set expiration**: `-1` (never expires)
7. **Click Add** to generate the API key
8. **Copy the generated API key** (e.g., `abc123def456`)

### Step 2: Test API Key with Curl

Once you have the API key, test it with curl:

```bash
# Test 1: Using /api route with apikey header
curl -X POST \
  "https://vectrustst01.manage.v2x.maximotest.gov2x.com/maximo/api/os/mxapiwodetail?action=wsmethod:changeStatus" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -H "apikey: YOUR_API_KEY_HERE" \
  -H "X-method-override: BULK" \
  -d '[{"wonum": "15643629", "status": "INPRG"}]' \
  -v

# Test 2: Using /api route with workorderid
curl -X POST \
  "https://vectrustst01.manage.v2x.maximotest.gov2x.com/maximo/api/os/mxapiwodetail/36148539" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -H "apikey: YOUR_API_KEY_HERE" \
  -d '{"status": "INPRG"}' \
  -v
```

### Step 3: Implement in Flask Application

Once the API key works with curl, we'll implement it in the Flask application:

```python
# In app.py - update the status change function
@app.route('/update-task-status', methods=['POST'])
def update_task_status():
    # Get API key from environment or config
    api_key = os.environ.get('MAXIMO_API_KEY') or 'YOUR_API_KEY_HERE'
    
    # Use /api route instead of /oslc
    workorderid_url = f"{token_manager.base_url}/api/os/mxapiwodetail/{task_workorderid}"
    
    # Include API key in headers
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "apikey": api_key
    }
    
    # Make the request
    update_response = requests.post(
        workorderid_url,
        json=status_data,
        headers=headers,
        timeout=(5.0, 30)
    )
```

## 🧪 Testing Plan

1. **Create API key** through Maximo web interface
2. **Test with curl** to verify API key works
3. **Update Flask application** to use API key
4. **Test status change** in the web application
5. **Verify status change** in Maximo

## 📚 References

- [IBM Maximo REST API Guide - API Keys](https://ibm-maximo-dev.github.io/maximo-restapi-documentation/authentication/apikey/)
- [IBM Support - Creating API keys in secure environments](https://www.ibm.com/support/pages/creating-and-using-rest-api-keys-secure-application-server-environment)
- [Medium - Create API Key in Maximo 7.6.1.X](https://medium.com/@fausto.busuito/create-an-api-key-for-an-user-in-maximo-7-6-1-x-5141c44bc2ac)

## 🎯 Next Steps

1. **Please create the API key** using the steps above
2. **Share the API key** so we can test and implement the solution
3. **We'll update the Flask application** to use the API key for status changes

This approach will solve the authentication issues and enable proper work order status changes through the REST API.
