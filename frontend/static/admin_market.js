// Admin Market Dashboard JavaScript

// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize the background particles
    initMarketParticles();
    
    // Initialize animated elements
    initProductsAnimations();
    
    // Initialize the products table and filters
    initProductsTable();
    
    // Initialize form validations and interactions
    initProductFormInteractions();
    
    // Initialize product stats counters
    initProductStatsCounters();
    
    // Show a demo success message
    setTimeout(() => {
        showMarketSuccessMessage('Welcome to the enhanced marketplace dashboard!');
    }, 1500);
});

// Initialize floating background particles
function initMarketParticles() {
    const container = document.querySelector('.market-particles-container');
    if (!container) return;
    
    // Create 15 particles with random properties
    for (let i = 0; i < 15; i++) {
        createMarketParticle(container);
    }
    
    // Add more particles every few seconds
    setInterval(() => {
        if (document.querySelectorAll('.market-particle').length < 20) {
            createMarketParticle(container);
        }
    }, 3000);
}

// Create a single floating particle
function createMarketParticle(container) {
    const particle = document.createElement('div');
    particle.className = 'market-particle';
    
    // Random size between 20 and 80px
    const size = Math.random() * 60 + 20;
    particle.style.width = `${size}px`;
    particle.style.height = `${size}px`;
    
    // Random position along the bottom of the screen
    particle.style.left = `${Math.random() * 100}%`;
    particle.style.bottom = `-${size}px`;
    
    // Random transparency
    particle.style.opacity = Math.random() * 0.5 + 0.1;
    
    // Random color variations (blues)
    const hue = 200 + Math.random() * 40;
    const saturation = 60 + Math.random() * 40;
    const lightness = 60 + Math.random() * 20;
    particle.style.backgroundColor = `hsla(${hue}, ${saturation}%, ${lightness}%, 0.15)`;
    
    // Random animation duration between 15 and 30 seconds
    const duration = Math.random() * 15 + 15;
    particle.style.animationDuration = `${duration}s`;
    
    // Random delay so particles don't all start at the same time
    particle.style.animationDelay = `${Math.random() * 10}s`;
    
    // Add to container
    container.appendChild(particle);
    
    // Remove particle after animation is complete
    setTimeout(() => {
        particle.remove();
    }, duration * 1000 + 10000);
}

// Animate table rows with a staggered effect
function initProductsAnimations() {
    // Animate table rows with delay
    const tableRows = document.querySelectorAll('.table-row-product-animated');
    tableRows.forEach((row, index) => {
        row.style.animationDelay = `${0.1 + index * 0.1}s`;
    });
}

// Initialize product table with search and filtering
function initProductsTable() {
    const searchInput = document.getElementById('productSearch');
    const filterButtons = document.querySelectorAll('.filter-product-btn');
    const tableRows = document.querySelectorAll('.products-table tbody tr:not(.no-data-row)');
    
    if (!searchInput || !tableRows.length) return;
    
    // Search functionality
    searchInput.addEventListener('input', function() {
        const searchTerm = this.value.toLowerCase();
        filterProductsTable(searchTerm, getCurrentProductFilter());
    });
    
    // Filter buttons
    filterButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            // Remove active class from all buttons
            filterButtons.forEach(b => b.classList.remove('active'));
            // Add active class to clicked button
            this.classList.add('active');
            
            // Filter the table
            filterProductsTable(searchInput.value.toLowerCase(), this.dataset.filter);
        });
    });
    
    // Set stock status colors
    document.querySelectorAll('.product-stock').forEach(stock => {
        const quantity = parseInt(stock.textContent);
        if (quantity <= 5) {
            stock.classList.add('low');
        } else if (quantity <= 20) {
            stock.classList.add('medium');
        } else {
            stock.classList.add('high');
        }
    });
    
    // Get current selected filter
    function getCurrentProductFilter() {
        const activeBtn = document.querySelector('.filter-product-btn.active');
        return activeBtn ? activeBtn.dataset.filter : 'all';
    }
    
    // Filter table based on search term and type filter
    function filterProductsTable(searchTerm, typeFilter) {
        tableRows.forEach(row => {
            const name = row.querySelector('td:nth-child(2)').textContent.toLowerCase();
            const type = row.querySelector('td:nth-child(3)').textContent.toLowerCase();
            
            const matchesSearch = name.includes(searchTerm);
            const matchesFilter = typeFilter === 'all' || type === typeFilter.toLowerCase();
            
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
        toggleNoResultsMessage(tableRows);
    }
    
    // Check if any rows are visible and toggle the no results message
    function toggleNoResultsMessage() {
        const visibleRows = Array.from(tableRows).filter(row => row.style.display !== 'none');
        const noDataRow = document.querySelector('.no-data-row');
        
        if (visibleRows.length === 0) {
            if (!noDataRow) {
                const tbody = document.querySelector('.products-table tbody');
                const tr = document.createElement('tr');
                tr.className = 'no-data-row';
                tr.innerHTML = `
                    <td colspan="10" class="no-data-cell">
                        <div class="no-data-message">
                            <i class="fas fa-shopping-basket"></i>
                            <p>No products match your search criteria</p>
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

// Form validations and interactions
function initProductFormInteractions() {
    // URL validation
    const urlInputs = document.querySelectorAll('input[type="url"]');
    urlInputs.forEach(input => {
        input.addEventListener('blur', function() {
            validateUrl(this);
        });
    });
    
    // Form validation
    const addProductForm = document.getElementById('addProductForm');
    if (addProductForm) {
        addProductForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // Basic validation
            const name = document.getElementById('productName');
            const type = document.getElementById('productType');
            const imageUrl = document.getElementById('productImageUrl');
            const buyUrl = document.getElementById('productBuyUrl');
            const price = document.getElementById('productPrice');
            const quantity = document.getElementById('productQuantity');
            const unit = document.getElementById('productUnit');
            
            let isValid = true;
            
            // Name validation
            if (name.value.trim().length < 3) {
                showValidationError(name, 'Product name must be at least 3 characters');
                isValid = false;
            } else {
                clearValidationError(name);
            }
            
            // Type validation
            if (type.value.trim().length < 2) {
                showValidationError(type, 'Product type must be provided');
                isValid = false;
            } else {
                clearValidationError(type);
            }
            
            // URL validations
            if (!isValidUrl(imageUrl.value)) {
                showValidationError(imageUrl, 'Please enter a valid image URL');
                isValid = false;
            } else {
                clearValidationError(imageUrl);
            }
            
            if (!isValidUrl(buyUrl.value)) {
                showValidationError(buyUrl, 'Please enter a valid buy URL');
                isValid = false;
            } else {
                clearValidationError(buyUrl);
            }
            
            // Number validations
            if (parseFloat(price.value) <= 0) {
                showValidationError(price, 'Price must be greater than 0');
                isValid = false;
            } else {
                clearValidationError(price);
            }
            
            if (parseInt(quantity.value) < 0) {
                showValidationError(quantity, 'Quantity cannot be negative');
                isValid = false;
            } else {
                clearValidationError(quantity);
            }
            
            // Unit validation
            if (unit.value.trim().length < 1) {
                showValidationError(unit, 'Unit must be provided (e.g., kg, piece)');
                isValid = false;
            } else {
                clearValidationError(unit);
            }
            
            // If form is valid, submit
            if (isValid) {
                // For demo purposes, show success message
                showMarketSuccessMessage(`Product ${name.value} has been added successfully!`);
                
                // In a real app, you'd submit the form here
                this.submit();
            }
        });
    }
    
    // URL validation helper
    function isValidUrl(url) {
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
        } else {
            clearValidationError(input);
        }
    }
    
    // Show validation error
    function showValidationError(input, message) {
        const formGroup = input.closest('.animated-product-form-group');
        let errorMessage = formGroup.querySelector('.validation-message');
        
        if (!errorMessage) {
            errorMessage = document.createElement('div');
            errorMessage.className = 'validation-message';
            formGroup.appendChild(errorMessage);
        }
        
        errorMessage.textContent = message;
        input.style.borderColor = '#e74c3c';
    }
    
    // Clear validation error
    function clearValidationError(input) {
        const formGroup = input.closest('.animated-product-form-group');
        const errorMessage = formGroup.querySelector('.validation-message');
        
        if (errorMessage) {
            errorMessage.textContent = '';
        }
        
        input.style.borderColor = '';
    }
}

// Initialize product stats counters with animation
function initProductStatsCounters() {
    const statsCards = document.querySelectorAll('.stat-card');
    
    statsCards.forEach(card => {
        const valueElement = card.querySelector('.stat-value');
        const finalValue = parseInt(valueElement.getAttribute('data-value'));
        
        animateCounter(valueElement, 0, finalValue, 1500);
    });
    
    function animateCounter(element, start, end, duration) {
        let startTimestamp = null;
        const step = (timestamp) => {
            if (!startTimestamp) startTimestamp = timestamp;
            const progress = Math.min((timestamp - startTimestamp) / duration, 1);
            const currentValue = Math.floor(progress * (end - start) + start);
            element.textContent = currentValue;
            
            if (progress < 1) {
                window.requestAnimationFrame(step);
            } else {
                element.textContent = end;
            }
        };
        
        window.requestAnimationFrame(step);
    }
}

// Show success message toast
function showMarketSuccessMessage(message) {
    // Remove any existing message
    const existingMessage = document.querySelector('.market-success-message');
    if (existingMessage) {
        existingMessage.remove();
    }
    
    // Create new message element
    const messageElement = document.createElement('div');
    messageElement.className = 'market-success-message';
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
