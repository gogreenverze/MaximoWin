#!/bin/bash

# Maximo Work Order Status Change Test Script
# Based on IBM Maximo NextGen REST API documentation

# Configuration
BASE_URL="https://vectrustst01.manage.v2x.maximotest.gov2x.com/maximo"
WORK_ORDER_NUM="15643629"
WORKORDER_ID="36148539"
NEW_STATUS="INPRG"

echo "🔧 Testing Maximo Work Order Status Change"
echo "=========================================="
echo "Work Order: $WORK_ORDER_NUM"
echo "Workorder ID: $WORKORDER_ID"
echo "New Status: $NEW_STATUS"
echo "Base URL: $BASE_URL"
echo ""

# Method 1: Using action=wsmethod:changeStatus (IBM recommended)
echo "📋 Method 1: Using action=wsmethod:changeStatus"
echo "URL: $BASE_URL/oslc/os/mxapiwodetail?action=wsmethod:changeStatus"
echo ""

curl -X POST \
  "$BASE_URL/oslc/os/mxapiwodetail?action=wsmethod:changeStatus" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -H "X-method-override: BULK" \
  -d '[{
    "wonum": "'$WORK_ORDER_NUM'",
    "status": "'$NEW_STATUS'"
  }]' \
  -v

echo ""
echo "----------------------------------------"
echo ""

# Method 2: Using workorderid directly
echo "📋 Method 2: Using workorderid directly"
echo "URL: $BASE_URL/oslc/os/mxapiwodetail/$WORKORDER_ID"
echo ""

curl -X POST \
  "$BASE_URL/oslc/os/mxapiwodetail/$WORKORDER_ID" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "'$NEW_STATUS'"
  }' \
  -v

echo ""
echo "----------------------------------------"
echo ""

# Method 3: Using POST with x-method-override PATCH
echo "📋 Method 3: Using POST with x-method-override PATCH"
echo "URL: $BASE_URL/oslc/os/mxapiwodetail/$WORKORDER_ID"
echo ""

curl -X POST \
  "$BASE_URL/oslc/os/mxapiwodetail/$WORKORDER_ID" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -H "X-method-override: PATCH" \
  -d '{
    "status": "'$NEW_STATUS'"
  }' \
  -v

echo ""
echo "=========================================="
echo "🔧 Test completed!"
