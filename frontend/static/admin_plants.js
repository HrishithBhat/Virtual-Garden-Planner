// Admin Plants Dashboard JavaScript

const PLANT_AI_ENDPOINTS = Object.freeze({
    suggest: '/api/admin/plants/ai/suggest',
    chat: '/api/admin/plants/ai/chat',
});

const PLANT_AI_FIELD_MAP = Object.freeze({
    name: 'plantName',
    scientific_name: 'plantScientificName',
    duration_days: 'plantDuration',
    type: 'plantType',
    photo_url: 'plantPhotoUrl',
    description: 'plantDescription',
    sunlight: 'plantSunlight',
    spacing_cm: 'plantSpacing',
    watering_needs: 'plantWatering',
    model_url: 'plantModelUrl',
    growth_height_cm: 'plantHeight',
    growth_width_cm: 'plantWidth',
});

const PLANT_AI_NUMERIC_FIELDS = new Set(['duration_days', 'spacing_cm', 'growth_height_cm', 'growth_width_cm']);

let plantAiState = {
    conversation: [],
    fieldsSnapshot: {},
    loading: false,
    duplicate: false,
    lastSuggestionKey: null,
    pendingSuggestionKey: null,
};

// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize the background particles
    initLeafParticles();
    
    // Initialize animated elements
    initPlantsAnimations();
    
    // Initialize the plants table and filters
    initPlantsTable();
    
    // Initialize form validations and interactions
    initPlantFormInteractions();
    
    // Initialize plant stats counters
    initPlantStatsCounters();
    
    // Initialize duration bars
    initDurationBars();

    // Initialize modal functionality
    initPlantModal();

    // Initialize AI assistant for add plant modal
    initPlantAiAssistant();

    // Show a demo success message
    setTimeout(() => {
        showPlantsSuccessMessage('Welcome to the enhanced plants dashboard!');
    }, 1500);
});

// Initialize floating leaf particles with enhanced variety and interactivity
function initLeafParticles() {
    const container = document.querySelector('.plants-particles-container');
    if (!container) return;
    
    // Create different types of plant particles with more variety
    const leafTypes = [
        // Leaves
        { class: 'leaf-particle', count: 8, icon: '🍃', weight: 3 },
        { class: 'leaf-particle', count: 4, icon: '🌿', weight: 2 },
        { class: 'leaf-particle', count: 3, icon: '🌱', weight: 2 },
        // Flowers
        { class: 'flower-particle', count: 4, icon: '🌸', weight: 2 },
        { class: 'flower-particle', count: 3, icon: '🌷', weight: 1 },
        { class: 'flower-particle', count: 3, icon: '🌹', weight: 1 },
        // Vegetables
        { class: 'vegetable-particle', count: 3, icon: '🥕', weight: 2 },
        { class: 'vegetable-particle', count: 2, icon: '🥦', weight: 1 },
        { class: 'vegetable-particle', count: 2, icon: '🥬', weight: 1 },
        // Fruits
        { class: 'fruit-particle', count: 3, icon: '🍎', weight: 2 },
        { class: 'fruit-particle', count: 2, icon: '🍊', weight: 1 },
        { class: 'fruit-particle', count: 2, icon: '🍇', weight: 1 }
    ];
    
    // Create initial particles
    leafTypes.forEach(type => {
        for (let i = 0; i < type.count; i++) {
            createLeafParticle(container, type.class, type.icon);
        }
    });
    
    // Interactive particles - add particles on click
    document.addEventListener('click', (e) => {
        // Don't add particles if clicking on interactive elements
        if (e.target.closest('button, a, input, select, textarea, label')) return;
        
        // Create a burst of particles on click
        const burstCount = Math.floor(Math.random() * 3) + 2; // 2-4 particles
        for (let i = 0; i < burstCount; i++) {
            // Create weighted random selection based on particle weight
            const weightedTypes = [];
            leafTypes.forEach(type => {
                for (let w = 0; w < type.weight; w++) {
                    weightedTypes.push(type);
                }
            });
            
            const randomType = weightedTypes[Math.floor(Math.random() * weightedTypes.length)];
            
            // Create particle at click position with a small offset
            const offsetX = Math.random() * 40 - 20;
            const offsetY = Math.random() * 40 - 20;
            createLeafParticle(
                container, 
                randomType.class, 
                randomType.icon, 
                e.clientX + offsetX, 
                e.clientY + offsetY,
                true
            );
        }
    });
    
    // Add more particles periodically
    setInterval(() => {
        if (document.querySelectorAll('[class*="-particle"]').length < 40) {
            // Create weighted random selection
            const weightedTypes = [];
            leafTypes.forEach(type => {
                for (let w = 0; w < type.weight; w++) {
                    weightedTypes.push(type);
                }
            });
            
            const randomType = weightedTypes[Math.floor(Math.random() * weightedTypes.length)];
            createLeafParticle(container, randomType.class, randomType.icon);
        }
    }, 2000);
    
    // Add seasonal particles based on time of day
    const hour = new Date().getHours();
    let seasonalIcon;
    
    // Morning: add sun particles
    if (hour >= 6 && hour < 10) {
        seasonalIcon = '☀️';
    }
    // Evening: add moon particles
    else if (hour >= 18 && hour < 22) {
        seasonalIcon = '🌙';
    }
    
    // Add seasonal particles if defined
    if (seasonalIcon) {
        setInterval(() => {
            if (Math.random() > 0.7) { // 30% chance
                createLeafParticle(container, 'seasonal-particle', seasonalIcon);
            }
        }, 5000);
    }
}

// Create a single floating particle with enhanced interactivity
function createLeafParticle(container, className = 'leaf-particle', icon = null, x = null, y = null, isClickGenerated = false) {
    const leaf = document.createElement('div');
    leaf.className = className;
    
    // Random size between 20 and 40px (larger for click-generated particles)
    const size = isClickGenerated ? Math.random() * 25 + 30 : Math.random() * 20 + 25;
    leaf.style.width = `${size}px`;
    leaf.style.height = `${size}px`;
    
    // If an icon is provided, use it instead of the SVG background
    if (icon) {
        leaf.innerHTML = `<span style="font-size: ${size}px">${icon}</span>`;
        leaf.style.display = 'flex';
        leaf.style.alignItems = 'center';
        leaf.style.justifyContent = 'center';
        leaf.style.background = 'none';
    }
    
    // Position logic - either at click position or random top position
    if (x !== null && y !== null) {
        // For click-generated particles, position at click and animate outward
        leaf.style.left = `${x}px`;
        leaf.style.top = `${y}px`;
        
        // For click particles, use a different animation
        leaf.style.animation = 'none';
        
        // Apply custom animation for click particles
        const angle = Math.random() * 360; // Random angle
        const distance = Math.random() * 150 + 50; // Random distance
        
        // Calculate end position based on angle and distance
        const endX = x + Math.cos(angle * Math.PI / 180) * distance;
        const endY = y + Math.sin(angle * Math.PI / 180) * distance;
        
        // Apply a spring-like animation
        leaf.animate([
            { transform: `translate(0, 0) rotate(0deg) scale(0.2)`, opacity: 0.2 },
            { transform: `translate(${distance/4}px, ${distance/4}px) rotate(${angle}deg) scale(1.2)`, opacity: 0.9, offset: 0.3 },
            { transform: `translate(${distance/2}px, ${distance/2}px) rotate(${angle*2}deg) scale(1)`, opacity: 0.7, offset: 0.6 },
            { transform: `translate(${distance}px, ${distance}px) rotate(${angle*3}deg) scale(0.5)`, opacity: 0 }
        ], {
            duration: Math.random() * 1500 + 1000, // 1-2.5s
            easing: 'cubic-bezier(0.175, 0.885, 0.32, 1.275)',
            fill: 'forwards'
        });
        
        // Remove click-generated particle after animation
        setTimeout(() => {
            leaf.remove();
        }, 2500);
    } else {
        // Standard particles - random position along the top of the screen
        leaf.style.left = `${Math.random() * 100}%`;
        leaf.style.top = `-${size}px`;
        
        // Random transparency and rotation
        leaf.style.opacity = Math.random() * 0.5 + 0.2;
        
        if (className === 'leaf-particle' && !icon) {
            // Random hue for different colored leaves
            const hue = 90 + Math.random() * 40; // green variations
            leaf.style.filter = `hue-rotate(${hue}deg)`;
        }
        
        // Random animation duration between 10 and 30 seconds
        const duration = Math.random() * 20 + 10;
        leaf.style.animationDuration = `${duration}s`;
        
        // Random delay so particles don't all start at the same time
        leaf.style.animationDelay = `${Math.random() * 5}s`;
        
        // Add some randomness to the animation path
        const pathVariation = Math.random() * 40 - 20; // -20 to +20
        leaf.style.setProperty('--path-variation', `${pathVariation}px`);
        
        // Random rotation speed
        const rotationSpeed = Math.random() * 10 + 5;
        leaf.style.setProperty('--rotation-speed', `${rotationSpeed}s`);
        
        // Add special animation for seasonal particles
        if (className === 'seasonal-particle') {
            leaf.style.zIndex = '5'; // Higher z-index for seasonal particles
            leaf.style.filter = 'drop-shadow(0 0 10px rgba(255,255,255,0.5))';
        }
        
        // Remove particle after animation is complete
        setTimeout(() => {
            leaf.remove();
        }, (duration + 5) * 1000);
    }
    
    // Add interaction - particles react to hover
    leaf.addEventListener('mouseenter', () => {
        if (!isClickGenerated) { // Only for regular floating particles
            // Apply a hover effect - make it grow and change direction
            leaf.style.transform = 'scale(1.5) rotate(45deg)';
            leaf.style.zIndex = '100';
            leaf.style.filter = 'brightness(1.3)';
            
            // Restore after leaving
            leaf.addEventListener('mouseleave', () => {
                leaf.style.transform = '';
                leaf.style.zIndex = '';
                leaf.style.filter = '';
            }, { once: true });
        }
    });
    
    // Add to container
    container.appendChild(leaf);
}

// Animate table rows with a staggered effect
function initPlantsAnimations() {
    // Animate table rows with delay
    const tableRows = document.querySelectorAll('.table-row-plant-animated');
    tableRows.forEach((row, index) => {
        row.style.animationDelay = `${0.1 + index * 0.1}s`;
    });
}

// Initialize duration bars
function initDurationBars() {
    const durationCells = document.querySelectorAll('.plant-duration');
    
    if (!durationCells.length) return;
    
    const durations = Array.from(durationCells).map(cell => {
        return parseInt(cell.getAttribute('data-days'));
    });
    
    const maxDuration = Math.max(...durations);
    
    durationCells.forEach(cell => {
        const days = parseInt(cell.getAttribute('data-days'));
        const percentage = (days / maxDuration) * 100;
        
        const bar = cell.querySelector('.duration-bar');
        if (bar) {
            setTimeout(() => {
                bar.style.width = `${percentage}%`;
            }, 500);
        }
    });
}

// Initialize plants table with search and filtering
function initPlantsTable() {
    const searchInput = document.getElementById('plantSearch');
    const filterButtons = document.querySelectorAll('.filter-plant-btn');
    const tableRows = document.querySelectorAll('.plants-table tbody tr:not(.no-data-row)');

    if (!searchInput || !tableRows.length) return;

    // Initial render ensures filters respect current active button state
    filterPlantsTable('', getCurrentPlantFilter());

    // Search functionality
    searchInput.addEventListener('input', function() {
        const searchTerm = this.value.toLowerCase();
        filterPlantsTable(searchTerm, getCurrentPlantFilter());
    });

    // Filter buttons
    filterButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            // Remove active class from all buttons
            filterButtons.forEach(b => b.classList.remove('active'));
            // Add active class to clicked button
            this.classList.add('active');

            // Filter the table
            filterPlantsTable(searchInput.value.toLowerCase(), this.dataset.filter);
        });
    });
    
    // Get current selected filter
    function getCurrentPlantFilter() {
        const activeBtn = document.querySelector('.filter-plant-btn.active');
        return activeBtn ? activeBtn.dataset.filter : 'all';
    }
    
    // Filter table based on search term and type filter
    function filterPlantsTable(searchTerm, typeFilter) {
        const normalizedFilter = (typeFilter || 'all').toLowerCase();
        tableRows.forEach(row => {
            const nameCell = row.querySelector('td:nth-child(2)');
            const scientificCell = row.querySelector('td:nth-child(3)');
            const typeBadge = row.querySelector('.plant-type-badge');
            const name = nameCell ? nameCell.textContent.toLowerCase() : '';
            const scientific = scientificCell ? scientificCell.textContent.toLowerCase() : '';
            const typeValue = typeBadge ? (typeBadge.dataset.type || typeBadge.textContent).trim().toLowerCase() : '';

            const matchesSearch = !searchTerm || name.includes(searchTerm) || scientific.includes(searchTerm);
            const matchesFilter = normalizedFilter === 'all' || typeValue === normalizedFilter;

            if (matchesSearch && matchesFilter) {
                row.style.display = '';
                // Re-apply animation
                row.style.animation = 'none';
                row.offsetHeight; // Trigger reflow
                row.style.animation = null;
            } else {
                row.style.display = 'none';
            }
        });

        // Show/hide no results message
        toggleNoResultsMessage();
    }

    // Check if any rows are visible and toggle the no results message
    function toggleNoResultsMessage() {
        const visibleRows = Array.from(tableRows).filter(row => row.style.display !== 'none');
        const noDataRow = document.querySelector('.no-data-row');
        
        if (visibleRows.length === 0) {
            if (!noDataRow) {
                const tbody = document.querySelector('.plants-table tbody');
                const tr = document.createElement('tr');
                tr.className = 'no-data-row';
                tr.innerHTML = `
                    <td colspan="7" class="no-data-cell">
                        <div class="no-data-message">
                            <i class="fas fa-seedling"></i>
                            <p>No plants match your search criteria</p>
                        </div>
                    </td>
                `;
                tbody.appendChild(tr);
            } else {
                noDataRow.style.display = '';
            }
        } else if (noDataRow) {
            noDataRow.style.display = 'none';
        }
    }
}

// Enhanced form validations and interactions with improved animations
function initPlantFormInteractions() {
    // Initial setup - add interactions to form fields
    const formInputs = document.querySelectorAll('.animated-plant-input, #plantDescription');
    const formGroups = document.querySelectorAll('.animated-plant-form-group');
    
    // Apply staggered animation to form groups
    formGroups.forEach((group, index) => {
        group.style.opacity = '0';
        group.style.transform = 'translateY(20px)';
        
        setTimeout(() => {
            group.style.transition = 'all 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275)';
            group.style.opacity = '1';
            group.style.transform = 'translateY(0)';
        }, 100 + (index * 100)); // Staggered effect
    });
    
    // Add focus and blur effects
    formInputs.forEach(input => {
        // Focus effect
        input.addEventListener('focus', function() {
            const formGroup = this.closest('.animated-plant-form-group');
            formGroup.classList.add('focused');
            
            // Create focus ripple
            const ripple = document.createElement('div');
            ripple.className = 'focus-ripple';
            ripple.style.cssText = `
                position: absolute;
                top: 50%;
                left: 0;
                width: 100%;
                height: 2px;
                background: linear-gradient(90deg, #4CAF50, transparent);
                transform: translateY(-50%);
                opacity: 0;
                transition: all 0.8s ease;
                z-index: 0;
            `;
            formGroup.appendChild(ripple);
            
            // Animate ripple
            setTimeout(() => {
                ripple.style.opacity = '1';
            }, 10);
            
            // Add growing plant icon
            const icon = formGroup.querySelector('.plant-input-icon i');
            if (icon) {
                icon.classList.add('fa-beat-fade');
            }
        });
        
        // Blur effect
        input.addEventListener('blur', function() {
            const formGroup = this.closest('.animated-plant-form-group');
            formGroup.classList.remove('focused');
            
            // Remove ripple
            const ripple = formGroup.querySelector('.focus-ripple');
            if (ripple) {
                ripple.style.opacity = '0';
                setTimeout(() => ripple.remove(), 800);
            }
            
            // Remove icon animation
            const icon = formGroup.querySelector('.plant-input-icon i');
            if (icon) {
                icon.classList.remove('fa-beat-fade');
            }
            
            // Validate on blur
            validateField(this);
        });
        
        // Input effect for real-time validation
        input.addEventListener('input', function() {
            // Remove error immediately when user starts typing
            const formGroup = this.closest('.animated-plant-form-group');
            const errorMessage = formGroup.querySelector('.validation-message');
            if (errorMessage && errorMessage.textContent) {
                errorMessage.style.opacity = '0.5';
            }
            
            // Real-time URL validation for the photo URL field
            if (this.id === 'plantPhotoUrl' && this.value.trim() !== '') {
                debounceValidateUrl(this);
            }
        });
    });
    
    // Debounced URL validation
    let urlValidationTimer;
    function debounceValidateUrl(input) {
        clearTimeout(urlValidationTimer);
        urlValidationTimer = setTimeout(() => {
            validateUrl(input);
        }, 500);
    }
    
    // URL validation
    const urlInput = document.querySelector('input[type="url"]');
    if (urlInput) {
        urlInput.addEventListener('blur', function() {
            validateUrl(this);
        });
        
        // URL preview (show image thumbnail when valid URL is entered)
        urlInput.addEventListener('input', debounceUrlPreview);
    }
    
    // URL preview helper
    let urlPreviewTimer;
    function debounceUrlPreview() {
        clearTimeout(urlPreviewTimer);
        urlPreviewTimer = setTimeout(() => {
            const url = urlInput.value.trim();
            const formGroup = urlInput.closest('.animated-plant-form-group');
            
            // Remove any existing preview
            const existingPreview = formGroup.querySelector('.url-preview');
            if (existingPreview) {
                existingPreview.remove();
            }
            
            // If URL is valid and looks like an image, show preview
            if (isValidUrl(url) && /\.(jpg|jpeg|png|gif|webp)$/i.test(url)) {
                const preview = document.createElement('div');
                preview.className = 'url-preview';
                preview.innerHTML = `
                    <img src="${url}" alt="Preview" style="
                        width: 50px;
                        height: 50px;
                        border-radius: 8px;
                        object-fit: cover;
                        position: absolute;
                        right: 15px;
                        top: 50%;
                        transform: translateY(-50%);
                        border: 2px solid rgba(76, 175, 80, 0.5);
                        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
                        opacity: 0;
                        transition: opacity 0.3s ease;
                    ">
                `;
                formGroup.style.position = 'relative';
                formGroup.appendChild(preview);
                
                // Animate in
                setTimeout(() => {
                    const img = preview.querySelector('img');
                    if (img) img.style.opacity = '1';
                }, 10);
                
                // Handle image load error
                preview.querySelector('img').onerror = function() {
                    this.src = 'https://via.placeholder.com/50?text=Error';
                    this.style.borderColor = 'rgba(231, 76, 60, 0.5)';
                };
            }
        }, 500);
    }
    
    // Form validation
    const addPlantForm = document.getElementById('addPlantForm');
    if (addPlantForm) {
        // Add hover effect to submit button
        const submitBtn = document.getElementById('submitPlantBtn');
        if (submitBtn) {
            submitBtn.addEventListener('mouseover', function() {
                // Add particle burst around the button on hover
                const rect = this.getBoundingClientRect();
                const centerX = rect.left + rect.width / 2;
                const centerY = rect.top + rect.height / 2;
                
                // Create small burst of particles
                for (let i = 0; i < 3; i++) {
                    setTimeout(() => {
                        // Create particles at corners
                        createLeafParticle(
                            document.querySelector('.plants-particles-container'),
                            'leaf-particle',
                            '🌱',
                            centerX + (Math.random() * 100 - 50),
                            centerY + (Math.random() * 60 - 30),
                            true
                        );
                    }, i * 150);
                }
            });
        }
    
        addPlantForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // Basic validation
            const name = document.getElementById('plantName');
            const scientificName = document.getElementById('plantScientificName');
            const duration = document.getElementById('plantDuration');
            const type = document.getElementById('plantType');
            const photoUrl = document.getElementById('plantPhotoUrl');
            const description = document.getElementById('plantDescription');
            
            // Validate all fields
            const nameValid = validateField(name);
            const sciNameValid = validateField(scientificName);
            const durationValid = validateField(duration);
            const typeValid = validateField(type);
            const urlValid = validateField(photoUrl);
            const descValid = validateField(description);
            
            const isValid = nameValid && sciNameValid && durationValid && 
                            typeValid && urlValid && descValid;
            
            // If form is valid, submit with animation
            if (isValid) {
                // Animate submit button
                const submitBtn = document.getElementById('submitPlantBtn');
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Adding...';
                submitBtn.disabled = true;
                
                // Create success animation
                const formRect = this.getBoundingClientRect();
                const centerX = formRect.left + formRect.width / 2;
                const centerY = formRect.top + formRect.height / 2;
                
                // Create burst of success particles
                for (let i = 0; i < 12; i++) {
                    setTimeout(() => {
                        const angle = (i / 12) * 360;
                        const distance = 100;
                        const x = centerX + Math.cos(angle * Math.PI / 180) * distance;
                        const y = centerY + Math.sin(angle * Math.PI / 180) * distance;
                        
                        const icons = ['🌱', '🌿', '🍃', '🌸', '🌷'];
                        const icon = icons[Math.floor(Math.random() * icons.length)];
                        
                        createLeafParticle(
                            document.querySelector('.plants-particles-container'),
                            'leaf-particle',
                            icon,
                            x, y,
                            true
                        );
                    }, i * 50);
                }
                
                // Show success message
                showPlantsSuccessMessage(`Plant ${name.value} has been added successfully!`);
                
                // In a real app, you'd submit the form after a delay for the animation
                setTimeout(() => {
                    this.submit();
                }, 800);
            } else {
                // Shake effect on the form for invalid submission
                this.classList.add('shake-error');
                setTimeout(() => {
                    this.classList.remove('shake-error');
                }, 500);
                
                // Scroll to the first error
                const firstError = this.querySelector('.validation-message');
                if (firstError) {
                    firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            }
        });
    }
    
    // Field validation function
    function validateField(input) {
        const id = input.id;
        let isValid = true;
        let message = '';
        
        switch(id) {
            case 'plantName':
                if (input.value.trim().length < 2) {
                    isValid = false;
                    message = 'Plant name must be at least 2 characters';
                }
                break;
                
            case 'plantScientificName':
                if (input.value.trim().length < 5) {
                    isValid = false;
                    message = 'Scientific name must be at least 5 characters';
                }
                break;
                
            case 'plantDuration':
                if (!input.value || parseInt(input.value) < 1) {
                    isValid = false;
                    message = 'Duration must be at least 1 day';
                }
                break;
                
            case 'plantType':
                if (input.value.trim().length < 2) {
                    isValid = false;
                    message = 'Plant type must be provided';
                } else {
                    // Suggest common types if it doesn't match
                    const commonTypes = ['vegetable', 'fruit', 'herb', 'flower'];
                    if (!commonTypes.includes(input.value.toLowerCase())) {
                        // Just a warning, not an error
                        showTypeWarning(input, commonTypes);
                    } else {
                        clearTypeWarning(input);
                    }
                }
                break;
                
            case 'plantPhotoUrl':
                if (!isValidUrl(input.value)) {
                    isValid = false;
                    message = 'Please enter a valid photo URL';
                }
                break;
                
            case 'plantDescription':
                if (input.value.trim().length < 10) {
                    isValid = false;
                    message = 'Description must be at least 10 characters';
                }
                break;
        }
        
        // Show or clear error message
        if (isValid) {
            clearValidationError(input);
        } else {
            showValidationError(input, message);
        }
        
        return isValid;
    }
    
    // Show warning for type field
    function showTypeWarning(input, commonTypes) {
        const formGroup = input.closest('.animated-plant-form-group');
        let warningEl = formGroup.querySelector('.type-warning');
        
        if (!warningEl) {
            warningEl = document.createElement('div');
            warningEl.className = 'type-warning';
            warningEl.style.cssText = `
                color: #e67e22;
                font-size: 0.85rem;
                margin-top: 5px;
                display: flex;
                align-items: center;
                gap: 5px;
                animation: fadeIn 0.3s ease;
            `;
            formGroup.appendChild(warningEl);
        }
        
        warningEl.innerHTML = `
            <i class="fas fa-info-circle"></i>
            <span>Suggestion: Common types are ${commonTypes.join(', ')}</span>
        `;
    }
    
    // Clear type warning
    function clearTypeWarning(input) {
        const formGroup = input.closest('.animated-plant-form-group');
        const warning = formGroup.querySelector('.type-warning');
        
        if (warning) {
            warning.remove();
        }
    }
    
    // URL validation helper
    function isValidUrl(url) {
        if (!url || url.trim() === '') return false;
        
        try {
            new URL(url);
            return true;
        } catch (e) {
            return false;
        }
    }
    
    // Validate URL on blur
    function validateUrl(input) {
        if (input.value && !isValidUrl(input.value)) {
            showValidationError(input, 'Please enter a valid URL');
            return false;
        } else {
            clearValidationError(input);
            return true;
        }
    }
    
    // Show validation error with enhanced animation
    function showValidationError(input, message) {
        const formGroup = input.closest('.animated-plant-form-group');
        let errorMessage = formGroup.querySelector('.validation-message');
        
        if (!errorMessage) {
            errorMessage = document.createElement('div');
            errorMessage.className = 'validation-message';
            errorMessage.style.opacity = '0';
            formGroup.appendChild(errorMessage);
            
            // Animate in
            setTimeout(() => {
                errorMessage.style.transition = 'all 0.3s ease';
                errorMessage.style.opacity = '1';
            }, 10);
        }
        
        // Add error icon and message with animation
        errorMessage.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${message}`;
        errorMessage.style.opacity = '1';
        
        // Add error styling to the input
        input.style.borderColor = '#e74c3c';
        input.style.boxShadow = '0 0 10px rgba(231, 76, 60, 0.3)';
        
        // Add error shake animation
        input.classList.add('error-shake');
        setTimeout(() => {
            input.classList.remove('error-shake');
        }, 500);
    }
    
    // Clear validation error with fade out animation
    function clearValidationError(input) {
        const formGroup = input.closest('.animated-plant-form-group');
        const errorMessage = formGroup.querySelector('.validation-message');
        
        if (errorMessage) {
            // Fade out animation
            errorMessage.style.opacity = '0';
            
            // Remove after animation completes
            setTimeout(() => {
                errorMessage.remove();
            }, 300);
        }
        
        // Clear error styling with transition
        input.style.transition = 'all 0.3s ease';
        input.style.borderColor = '';
        input.style.boxShadow = '';
    }
    
    // Add keyframe animation for the form shake effect
    const styleSheet = document.createElement('style');
    styleSheet.textContent = `
        @keyframes errorShake {
            0%, 100% { transform: translateX(0); }
            20%, 60% { transform: translateX(-5px); }
            40%, 80% { transform: translateX(5px); }
        }
        
        .error-shake {
            animation: errorShake 0.4s ease;
        }
        
        .shake-error {
            animation: errorShake 0.5s ease;
        }
        
        .animated-plant-form-group.focused .plant-input-icon {
            color: #4CAF50;
            transform: translateY(-50%) scale(1.2);
            filter: drop-shadow(0 0 5px rgba(76, 175, 80, 0.5));
        }
    `;
    document.head.appendChild(styleSheet);
}

// Initialize plant stats counters with enhanced animations
function initPlantStatsCounters() {
    const statsCards = document.querySelectorAll('.plant-stat-card');
    let observer;
    
    // Use Intersection Observer if available to trigger animations when visible
    if ('IntersectionObserver' in window) {
        observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    animateStatCard(entry.target);
                    observer.unobserve(entry.target); // Only animate once
                }
            });
        }, { threshold: 0.2 });
        
        // Observe all stat cards
        statsCards.forEach(card => {
            observer.observe(card);
        });
    } else {
        // Fallback for browsers without Intersection Observer
        statsCards.forEach(card => {
            setTimeout(() => animateStatCard(card), 500);
        });
    }
    
    // Function to animate a single stat card
    function animateStatCard(card) {
        const valueElement = card.querySelector('.plant-stat-value');
        const iconElement = card.querySelector('.plant-stat-icon');
        const labelElement = card.querySelector('.plant-stat-label');
        const finalValue = parseInt(valueElement.getAttribute('data-value'));
        
        // Add entrance animations
        iconElement.style.transform = 'scale(0)';
        valueElement.style.opacity = '0';
        labelElement.style.opacity = '0';
        
        // Animate icon first
        setTimeout(() => {
            iconElement.style.transition = 'transform 0.6s cubic-bezier(0.34, 1.56, 0.64, 1)';
            iconElement.style.transform = 'scale(1)';
            
            // When icon animation completes, animate counter
            setTimeout(() => {
                valueElement.style.transition = 'opacity 0.5s ease';
                valueElement.style.opacity = '1';
                animateCounter(valueElement, 0, finalValue, 1500);
                
                // Then animate label
                setTimeout(() => {
                    labelElement.style.transition = 'opacity 0.5s ease';
                    labelElement.style.opacity = '1';
                }, 200);
                
                // Add particle burst after counter completes
                setTimeout(() => {
                    // Create a burst of particles around the card
                    const rect = card.getBoundingClientRect();
                    const centerX = rect.left + rect.width / 2;
                    const centerY = rect.top + rect.height / 2;
                    
                    // Get the theme of the card to match particles
                    let particleIcon = '🌱';
                    const label = labelElement.textContent.toLowerCase();
                    
                    if (label.includes('vegetable')) particleIcon = '🥕';
                    else if (label.includes('fruit')) particleIcon = '🍎';
                    else if (label.includes('herb')) particleIcon = '🌿';
                    else if (label.includes('flower')) particleIcon = '🌸';
                    
                    // Create burst particles
                    for (let i = 0; i < 5; i++) {
                        setTimeout(() => {
                            createLeafParticle(
                                document.querySelector('.plants-particles-container'),
                                'leaf-particle',
                                particleIcon,
                                centerX + (Math.random() * 80 - 40),
                                centerY + (Math.random() * 80 - 40),
                                true
                            );
                        }, i * 100);
                    }
                }, 1500);
            }, 300);
        }, 300);
    }
    
    // Enhanced counter animation with easing
    function animateCounter(element, start, end, duration) {
        // Don't animate if the value is 0
        if (end === 0) {
            element.textContent = '0';
            return;
        }
        
        let startTimestamp = null;
        const step = (timestamp) => {
            if (!startTimestamp) startTimestamp = timestamp;
            
            // Calculate progress with easing
            const elapsed = timestamp - startTimestamp;
            const progress = Math.min(elapsed / duration, 1);
            
            // Apply easing function (cubic-bezier approximation)
            const easedProgress = cubicBezier(0.34, 1.56, 0.64, 1, progress);
            const currentValue = Math.floor(easedProgress * (end - start) + start);
            
            // Add animation class if the value changes
            if (element.textContent !== currentValue.toString()) {
                element.textContent = currentValue;
                element.classList.add('pulse-animation');
                
                // Remove animation class after animation completes
                setTimeout(() => {
                    element.classList.remove('pulse-animation');
                }, 300);
            }
            
            if (progress < 1) {
                window.requestAnimationFrame(step);
            } else {
                element.textContent = end;
            }
        };
        
        // Add keyframe animation for pulse effect
        const styleSheet = document.createElement('style');
        styleSheet.textContent = `
            @keyframes pulseValue {
                0% { transform: scale(1); }
                50% { transform: scale(1.2); }
                100% { transform: scale(1); }
            }
            
            .pulse-animation {
                animation: pulseValue 0.3s ease;
            }
        `;
        document.head.appendChild(styleSheet);
        
        window.requestAnimationFrame(step);
    }
    
    // Cubic-Bezier implementation for smoother easing
    function cubicBezier(p0, p1, p2, p3, t) {
        const term1 = Math.pow(1 - t, 3) * p0;
        const term2 = 3 * Math.pow(1 - t, 2) * t * p1;
        const term3 = 3 * (1 - t) * Math.pow(t, 2) * p2;
        const term4 = Math.pow(t, 3) * p3;
        
        return term1 + term2 + term3 + term4;
    }
}

// Initialize modal functionality
function initPlantModal() {
    const openModalBtn = document.getElementById('openAddPlantModal');
    const closeModalBtn = document.getElementById('closeAddPlantModal');
    const cancelBtn = document.getElementById('cancelAddPlant');
    const modalOverlay = document.getElementById('addPlantModal');
    
    if (!openModalBtn || !modalOverlay) return;
    
    // Open modal with animation
    openModalBtn.addEventListener('click', () => {
        modalOverlay.classList.add('active');
        document.body.style.overflow = 'hidden'; // Prevent scrolling

        document.dispatchEvent(new CustomEvent('plantModal:opened', {
            detail: {
                modalId: 'addPlantModal',
                formId: 'addPlantForm',
            },
        }));

        // Create particle burst around the button
        const rect = openModalBtn.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;
        
        // Create a burst of particles
        for (let i = 0; i < 8; i++) {
            setTimeout(() => {
                const angle = (i / 8) * 360;
                const distance = 60;
                const x = centerX + Math.cos(angle * Math.PI / 180) * distance;
                const y = centerY + Math.sin(angle * Math.PI / 180) * distance;
                
                createLeafParticle(
                    document.querySelector('.plants-particles-container'),
                    'leaf-particle',
                    '🌱',
                    x, y,
                    true
                );
            }, i * 50);
        }
        
        // Focus first input after animation completes
        setTimeout(() => {
            const firstInput = modalOverlay.querySelector('input');
            if (firstInput) firstInput.focus();
        }, 600);
    });
    
    // Close modal functions
    function closeModal() {
        if (modalOverlay.classList.contains('active')) {
            document.dispatchEvent(new CustomEvent('plantModal:closed', {
                detail: {
                    modalId: 'addPlantModal',
                    formId: 'addPlantForm',
                },
            }));
        }
        modalOverlay.classList.remove('active');
        document.body.style.overflow = ''; // Restore scrolling
    }
    
    // Close with X button
    if (closeModalBtn) {
        closeModalBtn.addEventListener('click', closeModal);
    }
    
    // Close with Cancel button
    if (cancelBtn) {
        cancelBtn.addEventListener('click', closeModal);
    }
    
    // Close with click outside
    modalOverlay.addEventListener('click', (e) => {
        if (e.target === modalOverlay) {
            closeModal();
        }
    });
    
    // Close with Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modalOverlay.classList.contains('active')) {
            closeModal();
        }
    });
    
    // Handle form submission inside modal
    const addPlantForm = document.getElementById('addPlantForm');
    if (addPlantForm) {
        addPlantForm.addEventListener('submit', (e) => {
            // Form validation is already handled in initPlantFormInteractions()
            // This will just handle closing the modal on success
            const isValid = validateModalForm();
            
            if (!isValid) {
                e.preventDefault();
                return;
            }
            
            // Show loading state
            const submitBtn = document.getElementById('submitPlantBtn');
            if (submitBtn) {
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Adding...';
                submitBtn.disabled = true;
            }
            
            // Don't close modal, form will submit and page will refresh
        });
    }
    
    function validateModalForm() {
        // Get form fields
        const name = document.getElementById('plantName');
        const scientificName = document.getElementById('plantScientificName');
        const duration = document.getElementById('plantDuration');
        const type = document.getElementById('plantType');
        const photoUrl = document.getElementById('plantPhotoUrl');
        const description = document.getElementById('plantDescription');
        
        // Validate each field (simple validation)
        let isValid = true;
        
        if (!name || !name.value.trim()) {
            isValid = false;
            showFieldError(name, 'Plant name is required');
        }
        
        if (!scientificName || !scientificName.value.trim()) {
            isValid = false;
            showFieldError(scientificName, 'Scientific name is required');
        }
        
        if (!duration || !duration.value || parseInt(duration.value) < 1) {
            isValid = false;
            showFieldError(duration, 'Valid duration is required');
        }
        
        if (!type || !type.value.trim()) {
            isValid = false;
            showFieldError(type, 'Plant type is required');
        }
        
        if (!photoUrl || !isValidUrl(photoUrl.value)) {
            isValid = false;
            showFieldError(photoUrl, 'Valid URL is required');
        }
        
        if (!description || !description.value.trim()) {
            isValid = false;
            showFieldError(description, 'Description is required');
        }
        
        return isValid;
    }
    
    function showFieldError(field, message) {
        if (!field) return;
        
        // Add error styling
        field.style.borderColor = '#e74c3c';
        field.style.boxShadow = '0 0 10px rgba(231, 76, 60, 0.3)';
        
        // Add shake animation
        field.classList.add('error-shake');
        setTimeout(() => {
            field.classList.remove('error-shake');
        }, 500);
        
        // Show error message
        const formGroup = field.closest('.animated-plant-form-group');
        if (formGroup) {
            let errorMsg = formGroup.querySelector('.validation-message');
            
            if (!errorMsg) {
                errorMsg = document.createElement('div');
                errorMsg.className = 'validation-message';
                formGroup.appendChild(errorMsg);
            }
            
            errorMsg.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${message}`;
        }
    }
    
    function isValidUrl(url) {
        if (!url || url.trim() === '') return false;
        
        try {
            new URL(url);
            return true;
        } catch (e) {
            return false;
        }
    }
}

function initPlantAiAssistant() {
    const modalOverlay = document.getElementById('addPlantModal');
    if (!modalOverlay) return;

    const form = document.getElementById('addPlantForm');
    const statusText = document.getElementById('plantAiStatusText');
    const duplicateAlert = document.getElementById('plantAiDuplicateAlert');
    const duplicateText = document.getElementById('plantAiDuplicateText');
    const similarMatches = document.getElementById('plantAiSimilarMatches');
    const chatLog = document.getElementById('plantAiChatLog');
    const placeholder = document.getElementById('plantAiPlaceholderMessage');
    const chatForm = document.getElementById('plantAiChatForm');
    const chatInput = document.getElementById('plantAiChatMessage');
    const refreshBtn = document.getElementById('plantAiRefresh');

    if (!form || !statusText || !chatForm || !chatInput || !refreshBtn) {
        return;
    }

    const fieldElements = buildFieldElementMap(form);

    document.addEventListener('plantModal:opened', () => {
        chatLog.scrollTop = chatLog.scrollHeight;
        if (!plantAiState.fieldsSnapshot.name) {
            statusText.textContent = 'Provide a plant name to start.';
        }
    });

    document.addEventListener('plantModal:closed', () => {
        resetPlantAiState(chatLog, placeholder, statusText, duplicateAlert, duplicateText, similarMatches, fieldElements);
    });

    Object.values(PLANT_AI_FIELD_MAP).forEach((fieldId) => {
        const element = document.getElementById(fieldId);
        if (!element) return;

        element.addEventListener('input', debounce(() => {
            plantAiState.fieldsSnapshot = captureFields(fieldElements);
            if (element.id === 'plantName' || element.id === 'plantPhotoUrl') {
                if (plantAiState.fieldsSnapshot.name) {
                    requestPlantSuggestion(
                        plantAiState.fieldsSnapshot,
                        statusText,
                        duplicateAlert,
                        duplicateText,
                        similarMatches,
                        chatLog,
                        placeholder,
                        fieldElements,
                    );
                }
            } else {
                updateStatus(statusText, 'Draft updated. AI is ready to refine further.');
            }
        }, 500));
    });

    chatForm.addEventListener('submit', (event) => {
        event.preventDefault();
        const message = chatInput.value.trim();
        if (!message) return;

        appendChatMessage(chatLog, 'user', message, placeholder);
        chatInput.value = '';
        chatInput.focus();

        requestChatCompletion(
            message,
            statusText,
            duplicateAlert,
            duplicateText,
            similarMatches,
            chatLog,
            fieldElements,
        );
    });

    refreshBtn.addEventListener('click', () => {
        if (plantAiState.loading) return;
        const nameField = document.getElementById('plantName');
        if (!nameField || !nameField.value.trim()) {
            shakeElement(nameField || refreshBtn);
            updateStatus(statusText, 'Enter a plant name before asking for a suggestion.');
            return;
        }
        plantAiState.fieldsSnapshot = captureFields(fieldElements);
        requestPlantSuggestion(
            plantAiState.fieldsSnapshot,
            statusText,
            duplicateAlert,
            duplicateText,
            similarMatches,
            chatLog,
            placeholder,
            fieldElements,
            true,
        );
    });
}

function buildFieldElementMap(form) {
    const map = {};
    Object.entries(PLANT_AI_FIELD_MAP).forEach(([fieldKey, fieldId]) => {
        const element = form.querySelector(`#${fieldId}`);
        if (element) map[fieldKey] = element;
    });
    return map;
}

function captureFields(fieldElements) {
    const values = {};
    Object.entries(fieldElements).forEach(([key, element]) => {
        if (!element) return;
        const rawValue = element.value.trim();
        if (PLANT_AI_NUMERIC_FIELDS.has(key)) {
            if (rawValue === '') {
                values[key] = null;
            } else {
                const numericValue = Number(rawValue);
                values[key] = Number.isFinite(numericValue) ? numericValue : null;
            }
        } else {
            values[key] = rawValue;
        }
    });
    return values;
}

function requestPlantSuggestion(
    fieldsSnapshot,
    statusText,
    duplicateAlert,
    duplicateText,
    similarMatches,
    chatLog,
    placeholder,
    fieldElements,
    force = false
) {
    const name = (fieldsSnapshot.name || '').trim();
    if (!name) {
        updateStatus(statusText, 'Provide a plant name to start.');
        return;
    }

    const photo = (fieldsSnapshot.photo_url || '').trim();
    const suggestionKey = `${name.toLowerCase()}|${photo}`;

    if (!force && (plantAiState.lastSuggestionKey === suggestionKey || plantAiState.pendingSuggestionKey === suggestionKey)) {
        return;
    }

    plantAiState.pendingSuggestionKey = suggestionKey;

    const payload = {
        name,
        photo_url: photo,
        scientific_name: (fieldsSnapshot.scientific_name || '').trim() || undefined,
    };

    setLoadingState(true, statusText, 'Searching plant knowledge base...');

    fetch(PLANT_AI_ENDPOINTS.suggest, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    })
        .then(handleFetchResponse)
        .then((data) => {
            applySuggestionResult(
                data,
                statusText,
                duplicateAlert,
                duplicateText,
                similarMatches,
                chatLog,
                placeholder
            );
        })
        .catch((error) => {
            plantAiState.lastSuggestionKey = null;
            updateStatus(statusText, error.message || 'Unable to reach AI assistant.');
            toggleDuplicateAlert(duplicateAlert, duplicateText, null);
            renderSimilarMatches(similarMatches, []);
        })
        .finally(() => {
            plantAiState.pendingSuggestionKey = null;
            setLoadingState(false, statusText);
        });
}

function requestChatCompletion(message, statusText, duplicateAlert, duplicateText, similarMatches, chatLog, fieldElements) {
    plantAiState.loading = true;
    updateStatus(statusText, 'Thinking...');

    const payload = {
        message,
        conversation: plantAiState.conversation,
        fields: captureFields(fieldElements),
    };

    fetch(PLANT_AI_ENDPOINTS.chat, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    })
        .then(handleFetchResponse)
        .then((data) => {
            plantAiState.conversation.push({ role: 'user', content: message });
            plantAiState.conversation.push({ role: 'assistant', content: data.message || '' });
            appendChatMessage(chatLog, 'assistant', data.message || '');
            toggleDuplicateAlert(duplicateAlert, duplicateText, data);
            renderSimilarMatches(similarMatches, data.similar_matches || []);
            const updates = filterAutoFillFields(data.field_updates || data.proposed_updates || {});
            if (updates && Object.keys(updates).length) {
                renderProposedUpdates(chatLog, updates, () => {
                    syncFieldsToForm(updates, fieldElements);
                    updateStatus(statusText, 'Applied suggested details.');
                });
            } else {
                updateStatus(statusText, 'No changes proposed.');
            }
        })
        .catch((error) => {
            plantAiState.conversation.push({ role: 'assistant', content: error.message || 'I could not process that request.' });
            appendChatMessage(chatLog, 'assistant', error.message || 'I could not process that request.');
            updateStatus(statusText, 'AI assistant encountered an issue.');
        })
        .finally(() => {
            plantAiState.loading = false;
        });
}

function handleFetchResponse(response) {
    if (!response.ok) {
        return response
            .json()
            .catch(() => ({ error: 'Unexpected error occurred.' }))
            .then((data) => {
                const message = data.error || data.message || 'Unexpected error occurred.';
                throw new Error(message);
            });
    }
    return response.json();
}

function applySuggestionResult(data, statusText, duplicateAlert, duplicateText, similarMatches, chatLog, placeholder) {
    plantAiState.conversation = [];
    plantAiState.fieldsSnapshot = data.fields || {};
    plantAiState.duplicate = Boolean(data.duplicate);

    toggleDuplicateAlert(duplicateAlert, duplicateText, data);
    renderSimilarMatches(similarMatches, data.similar_matches || []);

    if (data.message) {
        appendChatMessage(chatLog, 'assistant', data.message, placeholder);
    }

    const proposal = (data.web_details && data.web_details.field_updates) ? data.web_details.field_updates : (data.fields || {});
    const updates = filterAutoFillFields(proposal);
    if (updates && Object.keys(updates).length) {
        renderProposedUpdates(chatLog, updates, () => {
            const elements = buildFieldElementMap(document.getElementById('addPlantForm'));
            syncFieldsToForm(updates, elements);
            updateStatus(statusText, 'Applied suggested details.');
        });
    }

    if (data.duplicate) {
        updateStatus(statusText, 'Duplicate detected. You can adjust existing details.');
    } else {
        updateStatus(statusText, 'Review the proposed details and click Apply to fill the form.');
    }
}

function syncFieldsToForm(fields, fieldElements) {
    Object.entries(fields).forEach(([key, value]) => {
        const element = fieldElements[key];
        if (!element) return;

        if (element.type === 'number') {
            element.value = value === null || value === undefined ? '' : value;
        } else if (element.tagName === 'TEXTAREA') {
            element.value = value === null || value === undefined ? '' : value;
        } else {
            element.value = value === null || value === undefined ? '' : value;
        }

        element.dispatchEvent(new Event('input', { bubbles: true }));
    });
}

function appendChatMessage(chatLog, role, content, placeholder) {
    if (placeholder) {
        placeholder.hidden = true;
    }

    if (placeholder && !chatLog.contains(placeholder)) {
        chatLog.appendChild(placeholder);
    }

    const message = document.createElement('div');
    message.className = `plant-ai-chat-message ${role}`;
    message.innerHTML = `
        <div class="plant-ai-chat-avatar">
            <i class="${role === 'assistant' ? 'fas fa-robot' : 'fas fa-user'}"></i>
        </div>
        <div class="plant-ai-chat-bubble">
            <p>${escapeHtml(content)}</p>
        </div>
    `;

    chatLog.appendChild(message);
    chatLog.scrollTop = chatLog.scrollHeight;
}

function filterAutoFillFields(fields) {
    const out = {};
    Object.entries(fields || {}).forEach(([k, v]) => {
        if (k === 'name' || k === 'photo_url') return;
        out[k] = v;
    });
    return out;
}

function renderProposedUpdates(chatLog, updates, onAccept) {
    const wrapper = document.createElement('div');
    wrapper.className = 'plant-ai-chat-message assistant';

    const listItems = Object.entries(updates).map(([k, v]) => {
        const safe = escapeHtml(String(v ?? ''));
        return `<li><strong>${escapeHtml(k)}</strong>: ${safe}</li>`;
    }).join('');

    wrapper.innerHTML = `
        <div class="plant-ai-chat-avatar"><i class="fas fa-robot"></i></div>
        <div class="plant-ai-chat-bubble">
            <div style="margin-bottom:8px;">Apply these details to the form (excluding name and image)?</div>
            <ul class="ai-list">${listItems}</ul>
            <div style="display:flex; gap:8px; margin-top:10px;">
                <button class="btn btn-success small" type="button">Apply</button>
                <button class="btn btn-secondary small" type="button">Dismiss</button>
            </div>
        </div>`;

    chatLog.appendChild(wrapper);
    chatLog.scrollTop = chatLog.scrollHeight;

    const [applyBtn, dismissBtn] = wrapper.querySelectorAll('button');
    if (applyBtn) {
        applyBtn.addEventListener('click', () => {
            if (typeof onAccept === 'function') onAccept();
        });
    }
    if (dismissBtn) {
        dismissBtn.addEventListener('click', () => {
            wrapper.remove();
        });
    }
}

function toggleDuplicateAlert(duplicateAlert, duplicateText, data) {
    if (!duplicateAlert || !duplicateText) return;
    if (data && data.duplicate) {
        duplicateText.textContent = data.message || 'Duplicate detected. Existing data restored.';
        duplicateAlert.hidden = false;
    } else {
        duplicateAlert.hidden = true;
        duplicateText.textContent = '';
    }
}

function renderSimilarMatches(container, matches) {
    if (!container) return;
    container.innerHTML = '';
    if (!matches || !matches.length) {
        container.classList.remove('visible');
        return;
    }

    container.classList.add('visible');
    const title = document.createElement('p');
    title.className = 'plant-ai-similar-title';
    title.textContent = 'Close matches in database:';
    container.appendChild(title);

    const list = document.createElement('ul');
    list.className = 'plant-ai-similar-list';
    matches.forEach((match) => {
        const item = document.createElement('li');
        item.textContent = match;
        list.appendChild(item);
    });
    container.appendChild(list);
}

function setLoadingState(isLoading, statusText, loadingMessage) {
    plantAiState.loading = isLoading;
    if (isLoading && loadingMessage) {
        updateStatus(statusText, loadingMessage);
    }
}

function updateStatus(statusText, message) {
    if (!statusText) return;
    statusText.textContent = message;
}

function resetPlantAiState(chatLog, placeholder, statusText, duplicateAlert, duplicateText, similarMatches, fieldElements) {
    plantAiState = {
        conversation: [],
        fieldsSnapshot: captureFields(fieldElements),
        loading: false,
        duplicate: false,
    };

    if (placeholder) {
        placeholder.hidden = false;
    }
    if (chatLog) {
        chatLog.innerHTML = '';
        if (placeholder) {
            placeholder.hidden = false;
            chatLog.appendChild(placeholder);
        }
    }
    if (statusText) {
        statusText.textContent = 'Provide a plant name to start.';
    }
    if (duplicateAlert) {
        duplicateAlert.hidden = true;
    }
    if (duplicateText) {
        duplicateText.textContent = '';
    }
    if (similarMatches) {
        similarMatches.innerHTML = '';
        similarMatches.classList.remove('visible');
    }
}

function debounce(callback, delay) {
    let timeoutId;
    return function debounced(...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => {
            callback.apply(this, args);
        }, delay);
    };
}

function escapeHtml(html) {
    const div = document.createElement('div');
    div.textContent = html;
    return div.innerHTML;
}

function shakeElement(element) {
    if (!element) return;
    element.classList.add('shake');
    setTimeout(() => {
        element.classList.remove('shake');
    }, 600);
}

// Show success message toast
function showPlantsSuccessMessage(message) {
    // Remove any existing message
    const existingMessage = document.querySelector('.plants-success-message');
    if (existingMessage) {
        existingMessage.remove();
    }
    
    // Create new message element
    const messageElement = document.createElement('div');
    messageElement.className = 'plants-success-message';
    messageElement.innerHTML = `
        <i class="fas fa-check-circle"></i>
        <span>${message}</span>
    `;
    
    // Add to document
    document.body.appendChild(messageElement);
    
    // Trigger animation
    setTimeout(() => {
        messageElement.classList.add('show');
    }, 10);
    
    // Remove after 5 seconds
    setTimeout(() => {
        messageElement.classList.remove('show');
        
        // Remove from DOM after animation completes
        setTimeout(() => {
            messageElement.remove();
        }, 500);
    }, 5000);
}
