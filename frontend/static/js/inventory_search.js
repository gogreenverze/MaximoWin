/**
 * Inventory Search Functionality
 * 
 * Handles inventory search using MXAPIINVENTORY and MXAPIITEM APIs
 * with mobile-responsive UI and real-time search capabilities.
 * 
 * Author: Augment Agent
 * Date: 2025-01-27
 */

class InventorySearchManager {
    constructor() {
        this.currentSiteId = null;
        this.searchTimeout = null;
        this.lastSearchTerm = '';
        this.isSearching = false;
        
        this.initializeEventListeners();
    }

    initializeEventListeners() {
        // Search form submission
        document.getElementById('inventorySearchForm')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.performSearch();
        });

        // Real-time search with debouncing
        document.getElementById('inventorySearchTerm')?.addEventListener('input', (e) => {
            clearTimeout(this.searchTimeout);
            this.searchTimeout = setTimeout(() => {
                const searchTerm = e.target.value.trim();
                if (searchTerm.length >= 2 && searchTerm !== this.lastSearchTerm) {
                    this.performSearch();
                }
            }, 500);
        });

        // Enter key handling
        document.getElementById('inventorySearchTerm')?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.performSearch();
            }
        });
    }

    openSearchModal(siteId) {
        // Use provided siteId or fallback to global currentSiteId
        this.currentSiteId = siteId || (typeof currentSiteId !== 'undefined' ? currentSiteId : null);

        if (!this.currentSiteId || this.currentSiteId === 'UNKNOWN') {
            alert('Site ID not available. Please refresh the page and try again.');
            return;
        }

        console.log('Opening inventory search for site:', this.currentSiteId);

        // Reset form
        document.getElementById('inventorySearchTerm').value = '';
        document.getElementById('inventorySearchLimit').value = '20';

        // Reset results
        this.showInitialState();

        // Show modal
        const modalElement = document.getElementById('inventorySearchModal');

        if (!modalElement) {
            alert('Modal not found. Please check if the inventory search modal is properly included.');
            return;
        }

        const modal = new bootstrap.Modal(modalElement);
        modal.show();

        // Focus on search input
        setTimeout(() => {
            document.getElementById('inventorySearchTerm')?.focus();
        }, 500);
    }

    async performSearch() {
        const searchTerm = document.getElementById('inventorySearchTerm').value.trim();
        const limit = document.getElementById('inventorySearchLimit').value;

        if (!searchTerm) {
            this.showInitialState();
            return;
        }

        if (searchTerm.length < 2) {
            this.showError('Search term must be at least 2 characters long');
            return;
        }

        if (!this.currentSiteId) {
            this.showError('Site ID not available');
            return;
        }

        if (this.isSearching) {
            return; // Prevent multiple simultaneous searches
        }

        this.isSearching = true;
        this.lastSearchTerm = searchTerm;
        this.showLoading();

        try {
            const response = await fetch(`/api/inventory/search?q=${encodeURIComponent(searchTerm)}&siteid=${encodeURIComponent(this.currentSiteId)}&limit=${limit}`);
            const data = await response.json();

            if (data.success) {
                this.displayResults(data.items, data.metadata, searchTerm);
                this.updateSearchInfo(data);
            } else {
                this.showError(data.error || 'Search failed');
            }
        } catch (error) {
            console.error('Inventory search error:', error);
            this.showError('Network error occurred during search');
        } finally {
            this.isSearching = false;
        }
    }

    showLoading() {
        const resultsContainer = document.getElementById('inventorySearchResults');
        resultsContainer.innerHTML = `
            <div class="inventory-loading">
                <div class="spinner-border text-primary mb-3" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <div>Searching inventory...</div>
                <small class="text-muted">Please wait while we search for items</small>
            </div>
        `;
    }

    showInitialState() {
        const resultsContainer = document.getElementById('inventorySearchResults');
        resultsContainer.innerHTML = `
            <div class="text-center text-muted py-5">
                <i class="fas fa-search fa-3x mb-3"></i>
                <p class="mb-0">Enter a search term and click "Search" to find inventory items</p>
                <small class="text-muted">Search by item number or description</small>
            </div>
        `;
        
        document.getElementById('inventorySearchInfo').innerHTML = '';
    }

    showError(message) {
        const resultsContainer = document.getElementById('inventorySearchResults');
        resultsContainer.innerHTML = `
            <div class="inventory-error">
                <i class="fas fa-exclamation-triangle fa-2x mb-3"></i>
                <div class="fw-bold">Search Error</div>
                <div>${message}</div>
            </div>
        `;
    }

    displayResults(items, _metadata, searchTerm) {
        const resultsContainer = document.getElementById('inventorySearchResults');

        if (!items || items.length === 0) {
            resultsContainer.innerHTML = `
                <div class="inventory-empty">
                    <i class="fas fa-box-open fa-2x mb-3"></i>
                    <div class="fw-bold">No Items Found</div>
                    <div>No inventory items found for "${searchTerm}" in site ${this.currentSiteId}</div>
                    <small class="text-muted">Try a different search term or check the spelling</small>
                </div>
            `;
            return;
        }

        let html = '<div class="inventory-results-list">';
        
        items.forEach(item => {
            html += this.generateItemCard(item, searchTerm);
        });
        
        html += '</div>';
        resultsContainer.innerHTML = html;
    }

    generateItemCard(item, searchTerm) {
        const itemnum = item.itemnum || 'N/A';
        const description = item.description || 'No description available';
        const location = item.location || 'N/A';
        const siteid = item.siteid || 'N/A';
        
        // Highlight search terms
        const highlightedItemnum = this.highlightSearchTerm(itemnum, searchTerm);
        const highlightedDescription = this.highlightSearchTerm(description, searchTerm);

        // Format quantities and costs
        const curbaltotal = parseFloat(item.curbaltotal || 0);
        const avblbalance = parseFloat(item.avblbalance || 0);
        const avgcost = parseFloat(item.avgcost || 0);
        const lastcost = parseFloat(item.lastcost || 0);
        const stdcost = parseFloat(item.stdcost || 0);

        // Determine availability status
        const availabilityClass = avblbalance > 0 ? 'success' : (curbaltotal > 0 ? 'warning' : 'danger');
        const availabilityText = avblbalance > 0 ? 'Available' : (curbaltotal > 0 ? 'Reserved' : 'Out of Stock');

        return `
            <div class="inventory-item-card">
                <div class="inventory-item-header">
                    <div class="d-flex justify-content-between align-items-start">
                        <div class="flex-grow-1">
                            <div class="inventory-item-title">${highlightedItemnum}</div>
                            <div class="inventory-item-subtitle">
                                <i class="fas fa-map-marker-alt me-1"></i>${location} • ${siteid}
                                <span class="inventory-status-badge ${item.status?.toLowerCase() || 'active'} ms-2">
                                    ${item.status || 'ACTIVE'}
                                </span>
                            </div>
                        </div>
                        <div class="text-end">
                            <div class="inventory-detail-value ${availabilityClass}">
                                ${availabilityText}
                            </div>
                            <small class="text-muted">${avblbalance} of ${curbaltotal}</small>
                        </div>
                    </div>
                </div>
                <div class="inventory-item-body">
                    <div class="inventory-item-description">${highlightedDescription}</div>
                    
                    <div class="inventory-details-grid">
                        <div class="inventory-detail-item">
                            <div class="inventory-detail-label">Issue Unit</div>
                            <div class="inventory-detail-value">${item.issueunit || 'EA'}</div>
                        </div>
                        <div class="inventory-detail-item">
                            <div class="inventory-detail-label">Order Unit</div>
                            <div class="inventory-detail-value">${item.orderunit || 'EA'}</div>
                        </div>
                        <div class="inventory-detail-item">
                            <div class="inventory-detail-label">Current Balance</div>
                            <div class="inventory-detail-value highlight">${curbaltotal.toFixed(2)}</div>
                        </div>
                        <div class="inventory-detail-item">
                            <div class="inventory-detail-label">Available Balance</div>
                            <div class="inventory-detail-value ${availabilityClass}">${avblbalance.toFixed(2)}</div>
                        </div>
                        ${avgcost > 0 ? `
                        <div class="inventory-detail-item">
                            <div class="inventory-detail-label">Average Cost</div>
                            <div class="inventory-detail-value">${this.formatCurrency(avgcost, item.currency)}</div>
                        </div>` : ''}
                        ${lastcost > 0 ? `
                        <div class="inventory-detail-item">
                            <div class="inventory-detail-label">Last Cost</div>
                            <div class="inventory-detail-value">${this.formatCurrency(lastcost, item.currency)}</div>
                        </div>` : ''}
                        ${stdcost > 0 ? `
                        <div class="inventory-detail-item">
                            <div class="inventory-detail-label">Standard Cost</div>
                            <div class="inventory-detail-value">${this.formatCurrency(stdcost, item.currency)}</div>
                        </div>` : ''}
                        ${item.conditioncode ? `
                        <div class="inventory-detail-item">
                            <div class="inventory-detail-label">Condition Code</div>
                            <div class="inventory-detail-value">${item.conditioncode}</div>
                        </div>` : ''}
                        ${item.itemsetid ? `
                        <div class="inventory-detail-item">
                            <div class="inventory-detail-label">Item Set ID</div>
                            <div class="inventory-detail-value">${item.itemsetid}</div>
                        </div>` : ''}
                        ${item.nsn ? `
                        <div class="inventory-detail-item">
                            <div class="inventory-detail-label">NSN</div>
                            <div class="inventory-detail-value">${item.nsn}</div>
                        </div>` : ''}
                        ${item.commoditygroup ? `
                        <div class="inventory-detail-item">
                            <div class="inventory-detail-label">Commodity Group</div>
                            <div class="inventory-detail-value">${item.commoditygroup}</div>
                        </div>` : ''}
                        ${item.commodity ? `
                        <div class="inventory-detail-item">
                            <div class="inventory-detail-label">Commodity</div>
                            <div class="inventory-detail-value">${item.commodity}</div>
                        </div>` : ''}
                        ${item.abc ? `
                        <div class="inventory-detail-item">
                            <div class="inventory-detail-label">ABC Classification</div>
                            <div class="inventory-detail-value">${item.abc}</div>
                        </div>` : ''}
                        ${item.vendor ? `
                        <div class="inventory-detail-item">
                            <div class="inventory-detail-label">Vendor</div>
                            <div class="inventory-detail-value">${item.vendor}</div>
                        </div>` : ''}
                        ${item.manufacturer ? `
                        <div class="inventory-detail-item">
                            <div class="inventory-detail-label">Manufacturer</div>
                            <div class="inventory-detail-value">${item.manufacturer}</div>
                        </div>` : ''}
                    </div>

                    <!-- Add to Request Button -->
                    <div class="mt-3 d-flex justify-content-end">
                        <button type="button"
                                class="btn btn-primary btn-sm add-to-request-btn"
                                onclick="openMaterialRequestForm('${itemnum}', '${description.replace(/'/g, "\\'")}', '${location}', '${item.issueunit || 'EA'}')"
                                title="Add this item to material request">
                            <i class="fas fa-plus me-1"></i>Add to Request
                        </button>
                    </div>
                </div>
            </div>
        `;
    }

    highlightSearchTerm(text, searchTerm) {
        if (!text || !searchTerm) return text;
        
        const regex = new RegExp(`(${searchTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
        return text.replace(regex, '<span class="search-highlight">$1</span>');
    }

    formatCurrency(amount, currency = 'USD') {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: currency || 'USD',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(amount);
    }

    updateSearchInfo(data) {
        const infoElement = document.getElementById('inventorySearchInfo');
        const loadTime = data.metadata?.load_time || 0;
        const source = data.metadata?.source || 'api';
        const count = data.count || 0;

        infoElement.innerHTML = `
            <div class="search-stats">
                <span class="badge bg-primary me-2">${count} items</span>
                <span class="badge bg-secondary me-2">${loadTime.toFixed(3)}s</span>
                <span class="badge bg-info">${source}</span>
            </div>
        `;
    }
}

// Initialize the inventory search manager
const inventorySearchManager = new InventorySearchManager();

// Global function to open search modal (called from buttons)
function openInventorySearch(siteId) {
    // Fallback to global currentSiteId if not provided
    const finalSiteId = siteId || (typeof currentSiteId !== 'undefined' ? currentSiteId : null);

    if (!finalSiteId || finalSiteId === 'UNKNOWN') {
        alert('Site ID not available. Please refresh the page and try again.');
        return;
    }

    // Check if inventorySearchManager exists
    if (typeof inventorySearchManager === 'undefined') {
        alert('Inventory search manager not loaded. Please refresh the page.');
        return;
    }

    inventorySearchManager.openSearchModal(finalSiteId);
}

// Material Request Manager Class
class MaterialRequestManager {
    constructor() {
        this.currentWorkOrderNum = null;
        this.currentSiteId = null;
        this.selectedItem = null;
        this.isSubmitting = false;
        this.currentParentWonum = null;  // Parent work order number (e.g. 2021-1744762)
        this.currentTaskWonum = null;    // Task work order number (e.g. 2021-1835482)
        this.currentTaskId = null;       // Actual numeric task ID (e.g. 10, 20, 30)

        this.initializeEventListeners();
    }

    setTaskContext(parentWonum, taskWonum, taskId) {
        this.currentParentWonum = parentWonum;
        this.currentTaskWonum = taskWonum;
        this.currentTaskId = taskId;
        console.log(`Task context set: Parent WO ${parentWonum}, Task WO ${taskWonum}, Task ID ${taskId}`);
    }

    initializeEventListeners() {
        // Submit button click
        document.getElementById('submitMaterialRequest')?.addEventListener('click', () => {
            this.submitMaterialRequest();
        });

        // Direct request checkbox change
        document.getElementById('directRequest')?.addEventListener('change', ((e) => {
            const locationInput = document.getElementById('requestLocation');
            const helpText = document.getElementById('locationHelpText');

            if (e.target.checked) {
                // Direct request - disable location input
                locationInput.disabled = true;
                locationInput.value = '';
                locationInput.placeholder = 'Not required for direct request';
                if (helpText) helpText.textContent = 'Not required for direct request';
            } else {
                // Location-based request - enable location input and populate with item location
                locationInput.disabled = false;
                locationInput.placeholder = 'Enter location for material request';
                if (helpText) helpText.textContent = 'Required for location-based request';

                // Auto-populate with current item's location if available
                if (this.selectedItem && this.selectedItem.location && this.selectedItem.location !== 'N/A') {
                    locationInput.value = this.selectedItem.location;
                    if (helpText) helpText.textContent = `Auto-filled from item location: ${this.selectedItem.location}`;
                } else {
                    locationInput.value = '';
                    if (helpText) helpText.textContent = 'Please enter a location for this request';
                }
            }
        }).bind(this));

        // Form validation
        document.getElementById('requestQuantity')?.addEventListener('input', (e) => {
            const value = parseFloat(e.target.value);
            if (value <= 0) {
                e.target.setCustomValidity('Quantity must be greater than 0');
            } else {
                e.target.setCustomValidity('');
            }
        });
    }

    openRequestForm(itemnum, description, location, issueunit) {
        // Store selected item details
        this.selectedItem = {
            itemnum: itemnum,
            description: description,
            location: location,
            issueunit: issueunit
        };

        // Get current work order number from the page
        this.currentWorkOrderNum = this.getCurrentWorkOrderNum();
        this.currentSiteId = inventorySearchManager.currentSiteId;

        if (!this.currentWorkOrderNum) {
            alert('Work order number not found. Please refresh the page and try again.');
            return;
        }

        // Populate the form
        document.getElementById('selectedItemNum').textContent = itemnum;
        document.getElementById('selectedItemDesc').textContent = description;
        document.getElementById('selectedItemLocation').textContent = location;
        document.getElementById('selectedItemUnit').textContent = issueunit;

        // Reset form
        document.getElementById('materialRequestForm').reset();
        document.getElementById('requestQuantity').value = '1';
        document.getElementById('directRequest').checked = true;

        // Initialize location field for direct request
        const locationInput = document.getElementById('requestLocation');
        const helpText = document.getElementById('locationHelpText');
        locationInput.disabled = true;
        locationInput.value = '';
        locationInput.placeholder = 'Not required for direct request';
        if (helpText) helpText.textContent = 'Not required for direct request';

        // Initialize requestBy field with PersonID from Enhanced Profile
        this.initializeRequestByField();

        // Clear any previous messages
        document.getElementById('materialRequestInfo').innerHTML = '';

        // Show the modal
        const modal = new bootstrap.Modal(document.getElementById('materialRequestModal'));
        modal.show();
    }

    getCurrentWorkOrderNum() {
        // Try to get work order number from various sources
        // 1. From URL path
        const pathMatch = window.location.pathname.match(/\/workorder\/([^\/]+)/);
        if (pathMatch) {
            return pathMatch[1];
        }

        // 2. From page title or header
        const titleElement = document.querySelector('h1, .workorder-title, [data-wonum]');
        if (titleElement) {
            const wonum = titleElement.getAttribute('data-wonum') ||
                         titleElement.textContent.match(/\b\d{4}-\d{7}\b/)?.[0];
            if (wonum) return wonum;
        }

        // 3. From global variable if available
        if (typeof currentWorkOrderNum !== 'undefined') {
            return currentWorkOrderNum;
        }

        return null;
    }

    async submitMaterialRequest() {
        if (this.isSubmitting) return;

        // Validate form
        const form = document.getElementById('materialRequestForm');
        if (!form.checkValidity()) {
            form.reportValidity();
            return;
        }

        const quantity = parseFloat(document.getElementById('requestQuantity').value);
        const location = document.getElementById('requestLocation').value.trim();
        const directRequest = document.getElementById('directRequest').checked;
        const notes = document.getElementById('requestNotes').value.trim();
        const requestBy = document.getElementById('requestBy').value.trim();

        if (quantity <= 0) {
            alert('Please enter a valid quantity greater than 0');
            return;
        }

        if (!requestBy || requestBy === '') {
            alert('Please enter the person ID who is requesting this material');
            document.getElementById('requestBy').focus();
            return;
        }

        // Validate location for non-direct requests
        if (!directRequest && (!location || location.trim() === '')) {
            alert('Please enter a location for location-based requests, or check "Direct Request"');
            document.getElementById('requestLocation').focus();
            return;
        }

        // Set loading state
        this.setSubmitButtonLoading(true);
        this.isSubmitting = true;

        try {
            // Validate that we have task context (MANDATORY)
            if (this.currentTaskId === null || this.currentParentWonum === null || this.currentTaskWonum === null) {
                alert('Error: Task context not available. Please try again from the task section.');
                return;
            }

            const requestData = {
                wonum: this.currentParentWonum,  // Use PARENT work order number for top-level payload
                siteid: this.currentSiteId,
                itemnum: this.selectedItem.itemnum,
                quantity: quantity,
                taskid: this.currentTaskId,  // Use numeric task ID for Maximo API (MANDATORY)
                task_wonum: this.currentTaskWonum,  // Pass task wonum for backend validation
                location: directRequest ? null : (location ? location.trim() : null),
                directreq: directRequest,
                notes: notes ? notes.trim() : null,
                requestby: requestBy.trim()
            };

            console.log('Submitting material request:', requestData);

            const response = await fetch('/api/workorder/add-material-request', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestData)
            });

            const result = await response.json();

            if (result.success) {
                this.showSuccess('Material request submitted successfully!');

                // Close the modal after a short delay
                setTimeout(() => {
                    const modal = bootstrap.Modal.getInstance(document.getElementById('materialRequestModal'));
                    modal.hide();

                    // Refresh materials if we're on a work order detail page
                    if (typeof refreshMaterials === 'function') {
                        refreshMaterials();
                    }

                    // Refresh materials checks if we're on the enhanced work orders page
                    if (typeof refreshAllMaterialsChecks === 'function') {
                        refreshAllMaterialsChecks();
                    }
                }, 1500);
            } else {
                this.showError(result.error || 'Failed to submit material request');
            }
        } catch (error) {
            console.error('Material request submission error:', error);
            this.showError('Network error occurred while submitting request');
        } finally {
            this.setSubmitButtonLoading(false);
            this.isSubmitting = false;
        }
    }

    setSubmitButtonLoading(loading) {
        const button = document.getElementById('submitMaterialRequest');
        if (loading) {
            button.classList.add('loading');
            button.innerHTML = '<i class="fas fa-spinner me-1"></i>Submitting...';
            button.disabled = true;
        } else {
            button.classList.remove('loading');
            button.innerHTML = '<i class="fas fa-paper-plane me-1"></i>Submit Request';
            button.disabled = false;
        }
    }

    showSuccess(message) {
        const infoElement = document.getElementById('materialRequestInfo');
        infoElement.innerHTML = `<span class="request-success"><i class="fas fa-check-circle me-1"></i>${message}</span>`;
    }

    showError(message) {
        const infoElement = document.getElementById('materialRequestInfo');
        infoElement.innerHTML = `<span class="request-error"><i class="fas fa-exclamation-triangle me-1"></i>${message}</span>`;
    }

    async initializeRequestByField() {
        const requestByInput = document.getElementById('requestBy');

        try {
            // Set loading state
            requestByInput.value = '';
            requestByInput.placeholder = 'Loading person ID...';

            // Fetch user profile from Enhanced Profile service
            const response = await fetch('/api/enhanced-profile');

            if (response.ok) {
                const profile = await response.json();

                if (profile && profile.personid) {
                    requestByInput.value = profile.personid;
                    requestByInput.placeholder = 'Person ID from your profile';
                    console.log(`PersonID loaded from Enhanced Profile: ${profile.personid}`);
                } else {
                    // Fallback to displayname or username if personid not available
                    const fallbackValue = profile.displayname || profile.username || 'UNKNOWN';
                    requestByInput.value = fallbackValue;
                    requestByInput.placeholder = 'Person ID (fallback)';
                    console.warn('PersonID not found in profile, using fallback:', fallbackValue);
                }
            } else {
                throw new Error(`Failed to fetch profile: ${response.status}`);
            }
        } catch (error) {
            console.error('Error loading person ID:', error);
            requestByInput.value = 'UNKNOWN';
            requestByInput.placeholder = 'Error loading person ID';

            // Show error message in the form
            const formText = requestByInput.nextElementSibling;
            if (formText) {
                formText.innerHTML = '<span class="text-danger">Error loading person ID. Please enter manually.</span>';
                requestByInput.readOnly = false; // Allow manual entry
            }
        }
    }
}

// Initialize the material request manager
const materialRequestManager = new MaterialRequestManager();

// Global function to open material request form (called from inventory item buttons)
function openMaterialRequestForm(itemnum, description, location, issueunit) {
    materialRequestManager.openRequestForm(itemnum, description, location, issueunit);
}

// Log that the script has loaded
console.log('Inventory search script loaded successfully');
