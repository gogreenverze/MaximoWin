/**
 * Labor Search Manager
 * Handles labor code search functionality and labor addition to tasks
 */

class LaborSearchManager {
    constructor() {
        this.currentSiteId = null;
        this.taskContext = null;
        this.searchCache = new Map();
        this.isSearching = false;
        this.isLaborBeingSelected = false; // Flag to prevent form reset during labor selection

        // Timer functionality
        this.timerInterval = null;
        this.startTime = null;
        this.elapsedSeconds = 0;

        this.init();
    }
    
    init() {
        console.log('🔧 LABOR SEARCH: Initializing Labor Search Manager');
        
        // Bind event listeners
        this.bindEventListeners();
        
        // Initialize modal events
        this.initModalEvents();
    }
    
    bindEventListeners() {
        // Search form submission
        const searchForm = document.getElementById('laborSearchForm');
        if (searchForm) {
            searchForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.performSearch();
            });
        }
        
        // Clear search button
        const clearBtn = document.getElementById('clearLaborSearch');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => this.clearSearch());
        }
        
        // Clear cache button
        const clearCacheBtn = document.getElementById('clearLaborCacheBtn');
        if (clearCacheBtn) {
            clearCacheBtn.addEventListener('click', () => this.clearCache());
        }
        
        // Labor addition form submission
        const submitBtn = document.getElementById('submitLaborAddition');
        if (submitBtn) {
            submitBtn.addEventListener('click', () => this.submitLaborAddition());
        }
        
        // Real-time search on input
        const searchInput = document.getElementById('laborSearchTerm');
        if (searchInput) {
            let searchTimeout;
            searchInput.addEventListener('input', (e) => {
                clearTimeout(searchTimeout);
                const term = e.target.value.trim();
                if (term.length >= 2) {
                    searchTimeout = setTimeout(() => this.performSearch(), 500);
                } else if (term.length === 0) {
                    this.showEmptyState();
                }
            });
        }

        // Timer controls
        const startTimerBtn = document.getElementById('startTimerBtn');
        if (startTimerBtn) {
            startTimerBtn.addEventListener('click', () => this.startTimer());
        }

        const stopTimerBtn = document.getElementById('stopTimerBtn');
        if (stopTimerBtn) {
            stopTimerBtn.addEventListener('click', () => this.stopTimer());
        }

        // Time field change handlers for automatic hour calculation
        const startTimeField = document.getElementById('laborStartTime');
        const finishTimeField = document.getElementById('laborFinishTime');
        if (startTimeField && finishTimeField) {
            startTimeField.addEventListener('change', () => this.calculateHours());
            finishTimeField.addEventListener('change', () => this.calculateHours());
        }
    }
    
    initModalEvents() {
        // Reset modal when opened
        const laborModal = document.getElementById('laborSearchModal');
        if (laborModal) {
            laborModal.addEventListener('show.bs.modal', () => {
                this.showEmptyState();
                this.clearSearch();
            });
        }

        // Reset addition modal when opened - but only if no labor is being selected
        const additionModal = document.getElementById('laborAdditionModal');
        if (additionModal) {
            additionModal.addEventListener('show.bs.modal', () => {
                // Only reset if this is not triggered by labor selection
                if (!this.isLaborBeingSelected) {
                    this.resetAdditionForm();
                }
                // Reset the flag after modal is shown
                this.isLaborBeingSelected = false;

                // Ensure time dropdowns are populated
                this.populateTimeDropdowns();

                // Add event listeners for automatic hours calculation
                this.setupHoursCalculation();
            });
        }
    }
    
    setTaskContext(parentWonum, taskWonum, taskId) {
        this.taskContext = {
            parentWonum: parentWonum,
            taskWonum: taskWonum,
            taskId: taskId
        };
        console.log('🔧 LABOR SEARCH: Task context set:', this.taskContext);
    }
    
    setSiteId(siteId) {
        this.currentSiteId = siteId;
        console.log('🔧 LABOR SEARCH: Site ID set:', siteId);
    }
    
    async performSearch() {
        if (this.isSearching) return;
        
        const searchTerm = document.getElementById('laborSearchTerm')?.value?.trim();
        const limit = parseInt(document.getElementById('laborSearchLimit')?.value || '20');
        const craft = document.getElementById('laborCraftFilter')?.value?.trim();
        const skillLevel = document.getElementById('laborSkillFilter')?.value?.trim();
        
        if (!searchTerm || searchTerm.length < 2) {
            this.showError('Search term must be at least 2 characters');
            return;
        }
        
        if (!this.currentSiteId) {
            this.showError('Site ID is required for labor search');
            return;
        }
        
        this.isSearching = true;
        this.showLoading();
        
        try {
            const params = new URLSearchParams({
                search_term: searchTerm,
                site_id: this.currentSiteId,
                limit: limit.toString()
            });
            
            if (craft) params.append('craft', craft);
            if (skillLevel) params.append('skill_level', skillLevel);
            
            console.log(`🔍 LABOR SEARCH: Searching for "${searchTerm}" in site ${this.currentSiteId}`);
            
            const response = await fetch(`/api/labor/search?${params}`);
            const data = await response.json();
            
            if (data.success) {
                this.displayResults(data.labor_codes, data.metadata);
                console.log(`✅ LABOR SEARCH: Found ${data.labor_codes.length} labor codes`);
            } else {
                this.showError(data.error || 'Search failed');
            }
            
        } catch (error) {
            console.error('❌ LABOR SEARCH: Error:', error);
            this.showError('Network error occurred during search');
        } finally {
            this.isSearching = false;
        }
    }
    
    displayResults(laborCodes, metadata) {
        this.hideAllStates();
        
        const resultsDiv = document.getElementById('laborSearchResults');
        const tableBody = document.getElementById('laborResultsTableBody');
        const cardsContainer = document.getElementById('laborResultsCards');
        const statsDiv = document.getElementById('laborSearchStats');
        const infoDiv = document.getElementById('laborSearchInfo');
        
        if (!resultsDiv || !tableBody || !cardsContainer) return;
        
        // Update stats
        if (statsDiv) {
            const searchTime = metadata.search_time ? `${(metadata.search_time * 1000).toFixed(0)}ms` : 'N/A';
            const cacheStatus = metadata.cache_hit ? '(cached)' : '(fresh)';
            statsDiv.textContent = `${laborCodes.length} results in ${searchTime} ${cacheStatus}`;
        }
        
        // Update info
        if (infoDiv) {
            infoDiv.textContent = `Search: "${metadata.search_term}" | Site: ${metadata.site_id}`;
        }
        
        if (laborCodes.length === 0) {
            this.showEmptyResults();
            return;
        }
        
        // Populate desktop table with all MXAPILABOR details
        tableBody.innerHTML = laborCodes.map(labor => `
            <tr>
                <td><strong>${labor.laborcode || 'N/A'}</strong></td>
                <td>${labor.personid || 'N/A'}</td>
                <td>${labor.worksite || labor.siteid || 'N/A'}</td>
                <td>
                    <span class="badge ${labor.status === 'ACTIVE' ? 'bg-success' : 'bg-secondary'}">
                        ${labor.status || 'Unknown'}
                    </span>
                </td>
                <td>${labor.orgid || 'N/A'}</td>
                <td>${labor.laborid || 'N/A'}</td>
                <td>${labor.reportedhrs || labor.reported_hrs || 'N/A'}</td>
                <td>${labor.availfactor || labor.avail_factor || 'N/A'}</td>
                <td>
                    <span class="badge ${labor.assigned ? 'bg-warning' : 'bg-info'}">
                        ${labor.assigned ? 'Yes' : 'No'}
                    </span>
                </td>
                <td class="text-muted small">
                    ${labor.laborcraftrate && labor.laborcraftrate.length > 0 ?
                        labor.laborcraftrate.map(craft => `
                            <div class="mb-1">
                                <span class="badge ${craft.defaultcraft ? 'bg-primary' : 'bg-secondary'} me-1">
                                    ${craft.craft || 'N/A'}
                                </span>
                                <small>Rate: ${craft.rate || 0.0}</small>
                                ${craft.defaultcraft ? ' <small>(Default)</small>' : ''}
                            </div>
                        `).join('') :
                        `<div>
                            <span class="badge bg-secondary me-1">${labor.craft || 'N/A'}</span>
                            <small>Rate: ${labor.defaultrate || labor.standardrate || 'N/A'}</small>
                        </div>`
                    }
                </td>
                <td>
                    <button class="btn btn-sm btn-primary select-labor-btn"
                            data-labor='${JSON.stringify(labor)}'>
                        <i class="fas fa-plus me-1"></i>Select
                    </button>
                </td>
            </tr>
        `).join('');
        
        // Populate mobile cards with all MXAPILABOR details
        cardsContainer.innerHTML = laborCodes.map(labor => `
            <div class="card mb-3">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <h6 class="card-title mb-0">${labor.laborcode || 'N/A'}</h6>
                        <span class="badge ${labor.status === 'ACTIVE' ? 'bg-success' : 'bg-secondary'}">
                            ${labor.status || 'Unknown'}
                        </span>
                    </div>

                    <!-- Basic Info -->
                    <div class="row text-muted small mb-2">
                        <div class="col-6"><strong>Person ID:</strong> ${labor.personid || 'N/A'}</div>
                        <div class="col-6"><strong>Work Site:</strong> ${labor.worksite || labor.siteid || 'N/A'}</div>
                    </div>
                    <div class="row text-muted small mb-2">
                        <div class="col-6"><strong>Org ID:</strong> ${labor.orgid || 'N/A'}</div>
                        <div class="col-6"><strong>Labor ID:</strong> ${labor.laborid || 'N/A'}</div>
                    </div>
                    <div class="row text-muted small mb-2">
                        <div class="col-6"><strong>Reported Hrs:</strong> ${labor.reportedhrs || 'N/A'}</div>
                        <div class="col-6"><strong>Avail Factor:</strong> ${labor.availfactor || 'N/A'}</div>
                    </div>
                    <div class="row text-muted small mb-2">
                        <div class="col-12"><strong>Assigned:</strong> ${labor.assigned ? 'Yes' : 'No'}</div>
                    </div>

                    <!-- Craft and Rates -->
                    ${labor.laborcraftrate && labor.laborcraftrate.length > 0 ? `
                        <div class="mt-2">
                            <strong class="small">Craft & Rates:</strong>
                            ${labor.laborcraftrate.map(craft => `
                                <div class="small text-muted ms-2">
                                    <span class="badge ${craft.defaultcraft ? 'bg-primary' : 'bg-secondary'} me-1">
                                        ${craft.craft || 'N/A'}
                                    </span>
                                    Rate: ${craft.rate || 0.0}
                                    ${craft.defaultcraft ? ' (Default)' : ''}
                                </div>
                            `).join('')}
                        </div>
                    ` : `
                        <div class="row text-muted small mb-2">
                            <div class="col-6"><strong>Craft:</strong> ${labor.craft || 'N/A'}</div>
                            <div class="col-6"><strong>Rate:</strong> ${labor.defaultrate || labor.standardrate || 'N/A'}</div>
                        </div>
                    `}

                    <button class="btn btn-sm btn-primary select-labor-btn w-100 mt-3"
                            data-labor='${JSON.stringify(labor)}'>
                        <i class="fas fa-plus me-1"></i>Select Labor
                    </button>
                </div>
            </div>
        `).join('');
        
        // Bind select buttons
        document.querySelectorAll('.select-labor-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const laborData = JSON.parse(e.target.closest('.select-labor-btn').dataset.labor);
                this.selectLabor(laborData);
            });
        });
        
        resultsDiv.classList.remove('d-none');
    }
    
    selectLabor(laborData) {
        console.log('🔧 LABOR SEARCH: Selected labor:', laborData);
        console.log('🔧 LABOR SEARCH: Task context:', this.taskContext);
        console.log('🔧 LABOR SEARCH: Current site ID:', this.currentSiteId);

        if (!this.taskContext) {
            alert('No task context available. Please try again.');
            return;
        }

        // Set flag to prevent form reset when modal opens
        this.isLaborBeingSelected = true;

        // Hide search modal
        const searchModal = bootstrap.Modal.getInstance(document.getElementById('laborSearchModal'));
        if (searchModal) {
            searchModal.hide();
        }

        // Show addition modal
        this.showLaborAdditionModal(laborData);
    }
    
    showLaborAdditionModal(laborData) {
        console.log('🔧 LABOR MODAL: Opening addition modal with data:', laborData);

        // Populate selected labor info with all MXAPILABOR details
        const infoDiv = document.getElementById('selectedLaborInfo');
        console.log('🔧 LABOR MODAL: Found selectedLaborInfo div:', !!infoDiv);
        if (infoDiv) {
            infoDiv.innerHTML = `
                <div class="row">
                    <div class="col-md-6">
                        <strong>Labor Code:</strong> ${laborData.laborcode || 'N/A'}
                    </div>
                    <div class="col-md-6">
                        <strong>Person ID:</strong> ${laborData.personid || 'N/A'}
                    </div>
                    <div class="col-md-6 mt-2">
                        <strong>Work Site:</strong> ${laborData.worksite || laborData.siteid || 'N/A'}
                    </div>
                    <div class="col-md-6 mt-2">
                        <strong>Status:</strong> <span class="badge ${laborData.status === 'ACTIVE' ? 'bg-success' : 'bg-secondary'}">${laborData.status || 'Unknown'}</span>
                    </div>
                    <div class="col-md-6 mt-2">
                        <strong>Org ID:</strong> ${laborData.orgid || 'N/A'}
                    </div>
                    <div class="col-md-6 mt-2">
                        <strong>Labor ID:</strong> ${laborData.laborid || 'N/A'}
                    </div>
                    <div class="col-md-6 mt-2">
                        <strong>Reported Hrs:</strong> ${laborData.reportedhrs || 'N/A'}
                    </div>
                    <div class="col-md-6 mt-2">
                        <strong>Avail Factor:</strong> ${laborData.availfactor || 'N/A'}
                    </div>
                    <div class="col-12 mt-2">
                        <strong>Assigned:</strong> ${laborData.assigned ? 'Yes' : 'No'}
                    </div>
                    ${laborData.laborcraftrate && laborData.laborcraftrate.length > 0 ? `
                        <div class="col-12 mt-2">
                            <strong>Craft & Rates:</strong>
                            <div class="ms-2">
                                ${laborData.laborcraftrate.map(craft => `
                                    <div class="small">
                                        <span class="badge ${craft.defaultcraft ? 'bg-primary' : 'bg-secondary'} me-1">
                                            ${craft.craft || 'N/A'}
                                        </span>
                                        Rate: ${craft.rate || 0.0}
                                        ${craft.defaultcraft ? ' (Default)' : ''}
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    ` : `
                        <div class="col-md-6 mt-2">
                            <strong>Craft:</strong> ${laborData.craft || 'N/A'}
                        </div>
                        <div class="col-md-6 mt-2">
                            <strong>Rate:</strong> ${laborData.defaultrate || laborData.standardrate || 'N/A'}
                        </div>
                    `}
                </div>
            `;
        }
        
        // Set hidden fields
        console.log('🔧 LABOR MODAL: Setting form fields...');

        const selectedLaborCodeField = document.getElementById('selectedLaborCode');
        const taskWonumField = document.getElementById('taskWonum');
        const parentWonumField = document.getElementById('parentWonum');
        const taskIdField = document.getElementById('taskId');
        const siteIdInput = document.getElementById('laborSiteId');

        console.log('🔧 LABOR MODAL: Form fields found:', {
            selectedLaborCode: !!selectedLaborCodeField,
            taskWonum: !!taskWonumField,
            parentWonum: !!parentWonumField,
            taskId: !!taskIdField,
            laborSiteId: !!siteIdInput
        });

        if (selectedLaborCodeField) selectedLaborCodeField.value = laborData.laborcode || '';
        if (taskWonumField) taskWonumField.value = this.taskContext.taskWonum || '';
        if (parentWonumField) parentWonumField.value = this.taskContext.parentWonum || '';
        if (taskIdField) taskIdField.value = this.taskContext.taskId || '';
        if (siteIdInput) siteIdInput.value = this.currentSiteId || '';

        console.log('🔧 LABOR MODAL: Set values:', {
            laborcode: laborData.laborcode,
            taskWonum: this.taskContext.taskWonum,
            parentWonum: this.taskContext.parentWonum,
            taskId: this.taskContext.taskId,
            siteId: this.currentSiteId
        });
        
        // Pre-fill craft if available
        const craftInput = document.getElementById('laborCraft');
        if (craftInput && laborData.craft) {
            craftInput.value = laborData.craft;
        }

        // Pre-fill pay rate from labor data
        const payRateInput = document.getElementById('laborPayRate');
        if (payRateInput && laborData.laborcraftrate && laborData.laborcraftrate.length > 0) {
            // Use the default craft rate if available
            const defaultCraft = laborData.laborcraftrate.find(craft => craft.defaultcraft);
            if (defaultCraft && defaultCraft.rate) {
                payRateInput.value = defaultCraft.rate;
            }
        } else if (payRateInput && (laborData.defaultrate || laborData.standardrate)) {
            payRateInput.value = laborData.defaultrate || laborData.standardrate;
        }

        // Set current date as default for start date
        const startDateInput = document.getElementById('laborStartDate');
        if (startDateInput) {
            const today = new Date().toISOString().split('T')[0];
            startDateInput.value = today;
        }



        // Populate time dropdowns
        this.populateTimeDropdowns();

        // Show modal
        const additionModal = new bootstrap.Modal(document.getElementById('laborAdditionModal'));
        additionModal.show();
    }

    async submitLaborAddition() {
        const form = document.getElementById('laborAdditionForm');
        if (!form.checkValidity()) {
            form.reportValidity();
            return;
        }

        const submitBtn = document.getElementById('submitLaborAddition');
        const originalText = submitBtn.innerHTML;

        try {
            // Show loading state
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Adding Labor...';
            submitBtn.disabled = true;

            // Validate transtype is selected
            const transtype = document.getElementById('laborTransType').value;
            if (!transtype) {
                alert('Please select a transaction type before submitting.');
                return;
            }

            // Collect form data - using regularhrs not laborhrs
            const formData = {
                laborcode: document.getElementById('selectedLaborCode').value,
                regularhrs: parseFloat(document.getElementById('laborHours').value),
                siteid: document.getElementById('laborSiteId').value,
                taskid: parseInt(document.getElementById('taskId').value),
                parent_wonum: document.getElementById('parentWonum').value,
                craft: document.getElementById('laborCraft').value || null,
                startdate: document.getElementById('laborStartDate').value || null,
                starttime: document.getElementById('laborStartTime').value || null,
                finishdate: document.getElementById('laborFinishDate').value || null,
                finishtime: document.getElementById('laborFinishTime').value || null,
                payrate: parseFloat(document.getElementById('laborPayRate').value) || null,
                notes: document.getElementById('laborNotes').value || null,
                transtype: transtype
            };

            const taskWonum = document.getElementById('taskWonum').value;

            console.log('🔧 LABOR ADDITION: Submitting labor addition:', formData);

            const response = await fetch(`/api/task/${taskWonum}/add-labor`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(formData)
            });

            const result = await response.json();

            if (result.success) {
                console.log('✅ LABOR ADDITION: Success:', result);

                // Hide modal
                const modal = bootstrap.Modal.getInstance(document.getElementById('laborAdditionModal'));
                if (modal) {
                    modal.hide();
                }

                // Show success notification
                this.showNotification('success', result.message || 'Labor successfully added to task');

                // Refresh labor data if refresh function exists
                if (typeof refreshLabor === 'function') {
                    refreshLabor();
                }

            } else {
                console.error('❌ LABOR ADDITION: Error:', result.error);
                this.showNotification('error', result.error || 'Failed to add labor to task');
            }

        } catch (error) {
            console.error('❌ LABOR ADDITION: Network error:', error);
            this.showNotification('error', 'Network error occurred while adding labor');
        } finally {
            // Restore button state
            submitBtn.innerHTML = originalText;
            submitBtn.disabled = false;
        }
    }

    populateTimeDropdowns() {
        const startTimeSelect = document.getElementById('laborStartTime');
        const finishTimeSelect = document.getElementById('laborFinishTime');

        if (!startTimeSelect || !finishTimeSelect) {
            console.error('❌ POPULATE: Time dropdown elements not found');
            return;
        }

        console.log('🕐 POPULATE: Populating time dropdowns...');

        // Clear existing options (except the first placeholder option)
        startTimeSelect.innerHTML = '<option value="">Select start time</option>';
        finishTimeSelect.innerHTML = '<option value="">Select finish time</option>';

        let optionCount = 0;
        // Generate time options in 15-minute intervals
        for (let hour = 0; hour < 24; hour++) {
            for (let minute = 0; minute < 60; minute += 15) {
                const timeString = `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`;
                const displayTime = this.formatTimeDisplay(hour, minute);

                startTimeSelect.innerHTML += `<option value="${timeString}">${displayTime}</option>`;
                finishTimeSelect.innerHTML += `<option value="${timeString}">${displayTime}</option>`;
                optionCount++;
            }
        }

        console.log('🕐 POPULATE: Time dropdowns populated with', optionCount, 'options each');
    }

    formatTimeDisplay(hour, minute) {
        const period = hour >= 12 ? 'PM' : 'AM';
        const displayHour = hour === 0 ? 12 : hour > 12 ? hour - 12 : hour;
        const displayMinute = minute.toString().padStart(2, '0');
        return `${displayHour}:${displayMinute} ${period}`;
    }

    resetAdditionForm() {
        const form = document.getElementById('laborAdditionForm');
        if (form) {
            form.reset();
        }

        // Clear selected labor info
        const infoDiv = document.getElementById('selectedLaborInfo');
        if (infoDiv) {
            infoDiv.innerHTML = '<p class="text-muted">No labor selected</p>';
        }

        // Reset time dropdowns
        this.populateTimeDropdowns();

        // Set current date as default for start date
        const startDateInput = document.getElementById('laborStartDate');
        if (startDateInput) {
            const today = new Date().toISOString().split('T')[0];
            startDateInput.value = today;
        }

        // Reset timer
        this.resetTimer();
    }

    resetTimer() {
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
            this.timerInterval = null;
        }

        this.startTime = null;
        this.elapsedSeconds = 0;

        // Reset UI
        const startBtn = document.getElementById('startTimerBtn');
        const stopBtn = document.getElementById('stopTimerBtn');
        const display = document.getElementById('timerDisplay');

        if (startBtn) startBtn.disabled = false;
        if (stopBtn) stopBtn.disabled = true;
        if (display) display.textContent = 'Time Tracking 00:00:00';
    }

    clearSearch() {
        const form = document.getElementById('laborSearchForm');
        if (form) {
            form.reset();
        }
        this.showEmptyState();
    }

    async clearCache() {
        try {
            const response = await fetch('/api/labor/cache/clear', {
                method: 'POST'
            });

            const result = await response.json();

            if (result.success) {
                this.showNotification('success', result.message || 'Labor cache cleared');
                console.log('✅ LABOR CACHE: Cache cleared successfully');
            } else {
                this.showNotification('error', result.error || 'Failed to clear cache');
            }

        } catch (error) {
            console.error('❌ LABOR CACHE: Error clearing cache:', error);
            this.showNotification('error', 'Network error while clearing cache');
        }
    }

    showLoading() {
        this.hideAllStates();
        document.getElementById('laborSearchLoading')?.classList.remove('d-none');
    }

    showEmptyState() {
        this.hideAllStates();
        document.getElementById('laborSearchEmpty')?.classList.remove('d-none');
    }

    showEmptyResults() {
        this.hideAllStates();
        const resultsDiv = document.getElementById('laborSearchResults');
        if (resultsDiv) {
            resultsDiv.innerHTML = `
                <div class="text-center py-4">
                    <i class="fas fa-search fa-2x text-muted mb-3"></i>
                    <h5 class="text-muted">No Labor Codes Found</h5>
                    <p class="text-muted">Try adjusting your search criteria or filters.</p>
                </div>
            `;
            resultsDiv.classList.remove('d-none');
        }
    }

    showError(message) {
        this.hideAllStates();
        const errorDiv = document.getElementById('laborSearchError');
        const errorMsg = document.getElementById('laborSearchErrorMessage');

        if (errorDiv && errorMsg) {
            errorMsg.textContent = message;
            errorDiv.classList.remove('d-none');
        }
    }

    hideAllStates() {
        const states = [
            'laborSearchResults',
            'laborSearchEmpty',
            'laborSearchLoading',
            'laborSearchError'
        ];

        states.forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.classList.add('d-none');
            }
        });
    }

    showNotification(type, message) {
        // Create notification element
        const notification = document.createElement('div');
        let alertClass = 'alert-danger'; // default to error
        if (type === 'success') alertClass = 'alert-success';
        else if (type === 'info') alertClass = 'alert-info';
        else if (type === 'warning') alertClass = 'alert-warning';

        notification.className = `alert ${alertClass} alert-dismissible fade show position-fixed`;
        notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        // Add to page
        document.body.appendChild(notification);

        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 5000);
    }

    // Timer functionality methods
    startTimer() {
        if (this.timerInterval) {
            this.stopTimer();
        }

        this.startTime = new Date();
        this.elapsedSeconds = 0;

        // Set start time in form (SELECT dropdown)
        const startTimeField = document.getElementById('laborStartTime');
        if (startTimeField) {
            const timeString = this.formatTimeForSelect(this.startTime);

            // Ensure the time option exists in the dropdown
            this.ensureTimeOptionExists(startTimeField, timeString);

            // Set the value
            startTimeField.value = timeString;
            console.log('🕐 TIMER: Set start time field to:', timeString);

            // Add visual feedback
            startTimeField.style.backgroundColor = '#d4edda';
            setTimeout(() => {
                startTimeField.style.backgroundColor = '';
            }, 2000);

            // Trigger change event for hours calculation
            startTimeField.dispatchEvent(new Event('change'));
        } else {
            console.error('❌ TIMER: Start time field not found');
        }

        // Update UI
        const startBtn = document.getElementById('startTimerBtn');
        const stopBtn = document.getElementById('stopTimerBtn');
        if (startBtn) startBtn.disabled = true;
        if (stopBtn) stopBtn.disabled = false;

        // Start timer display update
        this.timerInterval = setInterval(() => {
            this.elapsedSeconds++;
            this.updateTimerDisplay();
        }, 1000);

        console.log('🕐 TIMER: Started at', this.startTime);
    }

    stopTimer() {
        if (!this.timerInterval) return;

        clearInterval(this.timerInterval);
        this.timerInterval = null;

        const endTime = new Date();

        // Set finish time in form (SELECT dropdown)
        const finishTimeField = document.getElementById('laborFinishTime');
        if (finishTimeField) {
            const timeString = this.formatTimeForSelect(endTime);

            // Ensure the time option exists in the dropdown
            this.ensureTimeOptionExists(finishTimeField, timeString);

            // Set the value
            finishTimeField.value = timeString;
            console.log('🕐 TIMER: Set finish time field to:', timeString);

            // Add visual feedback
            finishTimeField.style.backgroundColor = '#d4edda';
            setTimeout(() => {
                finishTimeField.style.backgroundColor = '';
            }, 2000);

            // Trigger change event for hours calculation
            finishTimeField.dispatchEvent(new Event('change'));
        } else {
            console.error('❌ TIMER: Finish time field not found');
        }

        // Calculate and set hours
        this.calculateHours();

        // Update UI
        const startBtn = document.getElementById('startTimerBtn');
        const stopBtn = document.getElementById('stopTimerBtn');
        if (startBtn) startBtn.disabled = false;
        if (stopBtn) stopBtn.disabled = true;

        console.log('🕐 TIMER: Stopped at', endTime, 'Duration:', this.elapsedSeconds, 'seconds');
    }

    updateTimerDisplay() {
        const display = document.getElementById('timerDisplay');
        if (display) {
            const hours = Math.floor(this.elapsedSeconds / 3600);
            const minutes = Math.floor((this.elapsedSeconds % 3600) / 60);
            const seconds = this.elapsedSeconds % 60;
            display.textContent = `Time Tracking ${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        }
    }

    formatTimeForSelect(date) {
        const hours = date.getHours().toString().padStart(2, '0');
        const minutes = date.getMinutes().toString().padStart(2, '0');
        return `${hours}:${minutes}`;
    }

    ensureTimeOptionExists(selectElement, timeValue) {
        // Check if the time option already exists
        const existingOption = Array.from(selectElement.options).find(option => option.value === timeValue);

        if (!existingOption) {
            // Create new option
            const option = document.createElement('option');
            option.value = timeValue;
            option.textContent = timeValue;

            // Insert in chronological order
            let inserted = false;
            for (let i = 1; i < selectElement.options.length; i++) { // Start from 1 to skip empty option
                if (selectElement.options[i].value > timeValue) {
                    selectElement.insertBefore(option, selectElement.options[i]);
                    inserted = true;
                    break;
                }
            }

            // If not inserted, append at the end
            if (!inserted) {
                selectElement.appendChild(option);
            }

            console.log('🕐 TIMER: Added time option:', timeValue);
        }
    }

    calculateHours() {
        const startTimeField = document.getElementById('laborStartTime');
        const finishTimeField = document.getElementById('laborFinishTime');
        const hoursField = document.getElementById('laborHours');

        if (!startTimeField || !finishTimeField || !hoursField) {
            console.error('❌ CALC: Missing form fields for hour calculation');
            return;
        }

        const startTime = startTimeField.value;
        const finishTime = finishTimeField.value;

        console.log('🕐 CALC: Calculating hours from', startTime, 'to', finishTime);

        if (startTime && finishTime) {
            const start = this.parseTimeString(startTime);
            const finish = this.parseTimeString(finishTime);

            if (start && finish) {
                let diffMs = finish - start;

                // Handle overnight work (finish time is next day)
                if (diffMs < 0) {
                    diffMs += 24 * 60 * 60 * 1000; // Add 24 hours
                    console.log('🕐 CALC: Detected overnight work, adjusted time difference');
                }

                const hours = diffMs / (1000 * 60 * 60);
                hoursField.value = hours.toFixed(2);

                console.log('🕐 CALC: Calculated hours:', hours.toFixed(2));

                // Add visual feedback for hours field
                hoursField.style.backgroundColor = '#d4edda';
                setTimeout(() => {
                    hoursField.style.backgroundColor = '';
                }, 2000);
            } else {
                console.error('❌ CALC: Failed to parse time strings');
            }
        } else {
            console.log('🕐 CALC: Start or finish time not set, skipping calculation');
        }
    }

    parseTimeString(timeStr) {
        if (!timeStr || timeStr === '') return null;

        try {
            const [hours, minutes] = timeStr.split(':').map(Number);
            if (isNaN(hours) || isNaN(minutes)) return null;

            const date = new Date();
            date.setHours(hours, minutes || 0, 0, 0);
            return date;
        } catch (error) {
            console.error('❌ TIMER: Error parsing time string:', timeStr, error);
            return null;
        }
    }

    setupHoursCalculation() {
        const startTimeField = document.getElementById('laborStartTime');
        const finishTimeField = document.getElementById('laborFinishTime');

        if (startTimeField && finishTimeField) {
            // Remove existing listeners to avoid duplicates
            startTimeField.removeEventListener('change', this.calculateHours.bind(this));
            finishTimeField.removeEventListener('change', this.calculateHours.bind(this));

            // Add new listeners
            startTimeField.addEventListener('change', this.calculateHours.bind(this));
            finishTimeField.addEventListener('change', this.calculateHours.bind(this));

            console.log('🕐 SETUP: Hours calculation listeners added');
        }
    }
}

// Global labor search manager instance
let laborSearchManager;

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    laborSearchManager = new LaborSearchManager();
});

// Global function to open labor search for a specific task
function openLaborSearchForTask(siteId, parentWonum, taskWonum, taskId) {
    if (!laborSearchManager) {
        console.error('❌ LABOR SEARCH: Manager not initialized');
        return;
    }

    // Set task context
    laborSearchManager.setTaskContext(parentWonum, taskWonum, taskId);
    laborSearchManager.setSiteId(siteId);

    // Show labor search modal
    const modal = new bootstrap.Modal(document.getElementById('laborSearchModal'));
    modal.show();

    console.log(`🔧 LABOR SEARCH: Opened for task ${taskWonum} in site ${siteId}`);
}

// Global function to refresh labor data after addition (following materials pattern)
function refreshLabor() {
    console.log('🔄 LABOR: Refreshing labor data after labor addition...');

    // Clear labor cache first
    fetch('/api/task/labor-records/cache/clear', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('✅ LABOR: Labor cache cleared successfully');

            // Refresh all loaded labor sections
            const loadedLaborButtons = document.querySelectorAll('.load-labor-btn');
            loadedLaborButtons.forEach(button => {
                const taskWonum = button.getAttribute('data-task-wonum');
                const taskStatus = button.getAttribute('data-task-status');
                const laborContent = document.getElementById(`labor-content-${taskWonum}`);

                // Only refresh if labor was already loaded (not showing the initial load button)
                if (laborContent && !laborContent.querySelector('.labor-loading') &&
                    laborContent.innerHTML.trim() !== '' &&
                    !laborContent.innerHTML.includes('Load Labor')) {

                    console.log(`🔄 LABOR: Refreshing labor for task ${taskWonum}`);
                    loadTaskLabor(taskWonum, taskStatus, button);
                }
            });

            showNotification('success', 'Labor data refreshed successfully');
        } else {
            console.error('❌ LABOR: Failed to clear labor cache:', data.error);
            showNotification('error', 'Failed to refresh labor cache');
        }
    })
    .catch(error => {
        console.error('❌ LABOR: Error clearing labor cache:', error);
        showNotification('error', 'Network error while refreshing labor data');
    });
}
