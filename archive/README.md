# Archive Folder

This folder contains files that have been moved from the root directory but are kept for reference. These files are no longer actively used in the project but may contain useful information or code snippets.

## Folder Structure

- **old_scripts**: Scripts that have been moved to the backend directory but kept for reference
- **test_data**: JSON response files, test data, and sample SQL files
- **testing_scripts**: Scripts used for testing various features

## Old Scripts

These scripts have been reorganized into the backend directory structure:

- **analyze_*.py**: Scripts for analyzing Maximo API responses
- **sync_*.py**: Scripts for syncing data from Maximo API to the local database
- **token_*.py**: Scripts for handling authentication and token management
- **test_*.py**: Scripts for testing API functionality
- **query_*.py**: Scripts for querying Maximo API
- **create_maximo_db.py**: Script for creating the Maximo offline database

## Test Data

This folder contains sample data and API responses used for testing:

- **\*_data.json**: Sample data files
- **\*_raw_response.json**: Raw API responses
- **\*_sync_response.json**: Sync API responses
- **insert_sample_data.sql**: SQL script for inserting sample data

## Testing Scripts

This folder contains scripts used for testing various features:

- **check_api_key.py**: Script for testing API key functionality
- **fetch_assets.py**: Script for fetching assets from Maximo API
- **examine_responses.py**: Script for examining API responses
