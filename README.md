# Lightning-Fast Maximo OAuth Login

A high-performance, mobile-first authentication module for IBM Maximo Asset Management with offline capabilities.

## Features

- ⚡ Lightning-fast authentication with Maximo
- 🔒 Secure OAuth token management
- 💾 Token caching for instant re-authentication
- 🔄 Connection pooling for optimized network performance
- 🌐 Mobile-first responsive design
- 🔍 Detailed performance metrics
- 📱 Offline capabilities with local database
- 🔑 API key support for improved performance

## Project Structure

The project is organized into the following directories:

- **backend**: Server-side code
  - **auth**: Authentication-related modules
  - **api**: API-related modules
  - **database**: Database-related modules
  - **sync**: Synchronization modules for offline capabilities

- **frontend**: Client-side code
  - **templates**: HTML templates
  - **static**: CSS, JS, and other static files

- **archive**: Archived files for reference
  - **old_scripts**: Scripts that have been moved to the backend
  - **test_data**: JSON response files and test data
  - **testing_scripts**: Testing scripts

- **docs**: Documentation files

## Getting Started

### Prerequisites

- Python 3.7+
- Flask
- Requests
- SQLite3

### Installation

1. Clone the repository
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the application:

```bash
python app.py
```

4. Open your browser and navigate to http://127.0.0.1:5004

## Database Explorer

To explore the offline database, run:

```bash
python explore_db.py
```

This will provide an interactive interface to:
- List all tables in the database
- View records from each table
- Execute predefined SQL queries
- Explore relationships between tables

## Documentation

For detailed documentation, see the [docs](docs/index.md) directory.

## Performance Optimizations

This module implements several key optimizations:

1. **Authentication URL Caching** - Eliminates network round-trips
2. **Connection Pooling** - Reuses TCP connections
3. **Token Storage and Reuse** - Enables instant re-authentication
4. **Background Authentication** - Provides immediate user feedback
5. **Optimized Network Settings** - Prevents hanging requests
6. **API Key Support** - Improves performance for data retrieval
7. **Offline Database** - Enables offline capabilities

## License

This project is licensed under the MIT License - see the LICENSE file for details.

---

*Developed by Praba Krishna @2023*
