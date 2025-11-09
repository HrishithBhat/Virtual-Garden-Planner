// Admin ML Training JavaScript

// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize the background particles
    initParticles();
    
    // Initialize animated elements
    initAnimations();
    
    // Initialize form validations
    initFormValidations();
    
    // Initialize dataset visualization
    initDatasetVisualization();
    
    // Show a demo success message
    setTimeout(() => {
        showSuccessMessage('ML Training dashboard loaded successfully!');
    }, 1500);
});

// Initialize floating background particles
function initParticles() {
    // Create particles container if it doesn't exist
    if (!document.querySelector('.ml-particles-container')) {
        const container = document.createElement('div');
        container.className = 'ml-particles-container';
        document.body.appendChild(container);
    }
    
    const container = document.querySelector('.ml-particles-container');
    
    // Create 10 particles with random properties
    for (let i = 0; i < 10; i++) {
        createParticle(container);
    }
    
    // Add more particles every few seconds
    setInterval(() => {
        if (document.querySelectorAll('.ml-particle').length < 15) {
            createParticle(container);
        }
    }, 3000);
}

// Create a single floating particle
function createParticle(container) {
    const particle = document.createElement('div');
    particle.className = 'ml-particle';
    
    // Random size between 20 and 60px
    const size = Math.random() * 40 + 20;
    particle.style.width = `${size}px`;
    particle.style.height = `${size}px`;
    
    // Random position along the bottom of the screen
    particle.style.left = `${Math.random() * 100}%`;
    particle.style.bottom = `-${size}px`;
    
    // Random transparency
    particle.style.opacity = Math.random() * 0.5 + 0.1;
    
    // Random color variations (greens)
    const hue = 120 + Math.random() * 40;
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
function initAnimations() {
    // Add animation class to table rows
    const tableRows = document.querySelectorAll('.users-table tbody tr');
    tableRows.forEach((row, index) => {
        row.classList.add('table-row-animated');
        row.style.animationDelay = `${0.1 + index * 0.1}s`;
    });
    
    // Add animation to forms
    const forms = document.querySelectorAll('.add-user-form');
    forms.forEach(form => {
        // Add focus and blur event listeners for form inputs
        const inputs = form.querySelectorAll('input, textarea');
        inputs.forEach(input => {
            // Skip file inputs and checkboxes
            if (input.type === 'file' || input.type === 'checkbox') return;
            
            // Add focus effect
            input.addEventListener('focus', function() {
                this.parentElement.classList.add('focused');
            });
            
            // Remove focus effect
            input.addEventListener('blur', function() {
                this.parentElement.classList.remove('focused');
                
                // Add filled class if input has value
                if (this.value.trim() !== '') {
                    this.classList.add('filled');
                } else {
                    this.classList.remove('filled');
                }
            });
            
            // Check if input already has value
            if (input.value.trim() !== '') {
                input.classList.add('filled');
            }
        });
    });
    
    // Add tooltip initialization
    initTooltips();
}

// Initialize tooltips
function initTooltips() {
    // Create tooltips for ML-specific elements
    addTooltip('epochs', 'Number of complete passes through the training dataset');
    addTooltip('lr', 'Learning rate controls how quickly the model adapts to the problem');
}

// Add a tooltip to an element
function addTooltip(elementId, text) {
    const element = document.getElementById(elementId);
    if (!element) return;
    
    const label = element.closest('.form-group').querySelector('label');
    if (!label) return;
    
    const tooltip = document.createElement('span');
    tooltip.className = 'help-tooltip';
    tooltip.innerHTML = `<i class="fas fa-question-circle"></i><span class="tooltip-text">${text}</span>`;
    
    label.appendChild(tooltip);
}

// Form validations
function initFormValidations() {
    // Get upload form
    const uploadForm = document.querySelector('form[action*="ml_upload"]');
    if (uploadForm) {
        uploadForm.addEventListener('submit', function(e) {
            const labelInput = this.querySelector('input[name="label"]');
            const fileInput = this.querySelector('input[type="file"]');
            
            let isValid = true;
            
            // Validate label
            if (labelInput.value.trim() === '') {
                showValidationError(labelInput, 'Please enter a class label');
                isValid = false;
            } else {
                clearValidationError(labelInput);
            }
            
            // Validate file input
            if (fileInput.files.length === 0) {
                showValidationError(fileInput, 'Please select at least one image');
                isValid = false;
            } else {
                clearValidationError(fileInput);
                
                // Show loading indicator while uploading
                if (isValid) {
                    showLoading();
                }
            }
            
            if (!isValid) {
                e.preventDefault();
            }
        });
    }
    
    // Get train model form
    const trainForm = document.querySelector('form[action*="ml_train"]');
    if (trainForm) {
        trainForm.addEventListener('submit', function(e) {
            const epochsInput = document.getElementById('epochs');
            const lrInput = document.getElementById('lr');
            
            let isValid = true;
            
            // Validate epochs
            if (Number(epochsInput.value) < 1 || Number(epochsInput.value) > 50) {
                showValidationError(epochsInput, 'Epochs must be between 1 and 50');
                isValid = false;
            } else {
                clearValidationError(epochsInput);
            }
            
            // Validate learning rate
            if (Number(lrInput.value) <= 0 || Number(lrInput.value) > 1) {
                showValidationError(lrInput, 'Learning rate must be between 0 and 1');
                isValid = false;
            } else {
                clearValidationError(lrInput);
            }
            
            if (isValid) {
                // Show loading indicator for training
                showLoading('Training model... This may take a few minutes.');
            } else {
                e.preventDefault();
            }
        });
    }
    
    // Handle file input styling
    const fileInputs = document.querySelectorAll('input[type="file"]');
    fileInputs.forEach(input => {
        input.addEventListener('change', function() {
            if (this.files.length > 0) {
                const fileCount = this.files.length;
                const fileCountText = fileCount === 1 ? '1 file selected' : `${fileCount} files selected`;
                
                // Create or update file count display
                let fileCountDisplay = this.parentElement.querySelector('.file-count');
                if (!fileCountDisplay) {
                    fileCountDisplay = document.createElement('div');
                    fileCountDisplay.className = 'file-count';
                    this.parentElement.appendChild(fileCountDisplay);
                }
                
                fileCountDisplay.textContent = fileCountText;
                fileCountDisplay.style.display = 'block';
            }
        });
    });
}

// Show validation error
function showValidationError(input, message) {
    const formGroup = input.closest('.form-group');
    let errorMessage = formGroup.querySelector('.validation-message');
    
    if (!errorMessage) {
        errorMessage = document.createElement('div');
        errorMessage.className = 'validation-message';
        errorMessage.style.color = '#dc3545';
        errorMessage.style.fontSize = '0.85rem';
        errorMessage.style.marginTop = '5px';
        formGroup.appendChild(errorMessage);
    }
    
    errorMessage.textContent = message;
    input.style.borderColor = '#dc3545';
    
    // Shake animation
    input.style.animation = 'shake 0.5s';
    setTimeout(() => {
        input.style.animation = '';
    }, 500);
}

// Clear validation error
function clearValidationError(input) {
    const formGroup = input.closest('.form-group');
    const errorMessage = formGroup.querySelector('.validation-message');
    
    if (errorMessage) {
        errorMessage.textContent = '';
    }
    
    input.style.borderColor = '';
}

// Show loading indicator
function showLoading(message = 'Processing...') {
    // Remove any existing loading indicator
    const existingIndicator = document.querySelector('.loading-indicator');
    if (existingIndicator) {
        existingIndicator.remove();
    }
    
    // Create loading indicator
    const loadingIndicator = document.createElement('div');
    loadingIndicator.className = 'loading-indicator';
    loadingIndicator.innerHTML = `
        <div class="spinner"></div>
        <p>${message}</p>
    `;
    
    // Add to document
    document.body.appendChild(loadingIndicator);
    
    // Show with animation
    setTimeout(() => {
        loadingIndicator.classList.add('visible');
    }, 10);
}

// Hide loading indicator
function hideLoading() {
    const loadingIndicator = document.querySelector('.loading-indicator');
    if (loadingIndicator) {
        loadingIndicator.classList.remove('visible');
        
        // Remove from DOM after animation completes
        setTimeout(() => {
            loadingIndicator.remove();
        }, 300);
    }
}

// Initialize dataset visualization
function initDatasetVisualization() {
    const table = document.querySelector('.users-table');
    if (!table) return;
    
    // Get all rows except header and empty state
    const rows = Array.from(table.querySelectorAll('tbody tr')).filter(row => {
        return row.cells.length > 1; // Filter out the "No images uploaded yet" row
    });
    
    if (rows.length === 0) return;
    
    // Create dataset visualization container
    const visualizationContainer = document.createElement('div');
    visualizationContainer.className = 'dataset-summary';
    
    // Find the max count to scale the bars
    let maxCount = 0;
    rows.forEach(row => {
        const count = parseInt(row.cells[1].textContent);
        if (count > maxCount) maxCount = count;
    });
    
    // Create bars for each class
    rows.forEach(row => {
        const className = row.cells[0].textContent;
        const count = parseInt(row.cells[1].textContent);
        const percentage = Math.round((count / maxCount) * 100);
        
        const barContainer = document.createElement('div');
        
        const labelDiv = document.createElement('div');
        labelDiv.className = 'dataset-label';
        labelDiv.innerHTML = `
            <span>${className}</span>
            <span>${count} images</span>
        `;
        
        const barDiv = document.createElement('div');
        barDiv.className = 'dataset-bar';
        
        const barFill = document.createElement('div');
        barFill.className = 'dataset-bar-fill';
        barFill.style.width = '0%'; // Start at 0 for animation
        
        barDiv.appendChild(barFill);
        barContainer.appendChild(labelDiv);
        barContainer.appendChild(barDiv);
        visualizationContainer.appendChild(barContainer);
        
        // Animate the bar width
        setTimeout(() => {
            barFill.style.width = `${percentage}%`;
        }, 100);
    });
    
    // Insert after the table
    table.parentNode.insertBefore(visualizationContainer, table.nextSibling);
}

// Show success message toast
function showSuccessMessage(message) {
    // Remove any existing message
    const existingMessage = document.querySelector('.success-message');
    if (existingMessage) {
        existingMessage.remove();
    }
    
    // Create new message element
    const messageElement = document.createElement('div');
    messageElement.className = 'success-message';
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

// Add keyframe animation for shake effect
const styleSheet = document.createElement('style');
styleSheet.textContent = `
@keyframes shake {
    0%, 100% { transform: translateX(0); }
    10%, 30%, 50%, 70%, 90% { transform: translateX(-5px); }
    20%, 40%, 60%, 80% { transform: translateX(5px); }
}

.form-group.focused {
    transform: translateY(-3px);
    transition: transform 0.3s ease;
}

input.filled, textarea.filled {
    background-color: rgba(76, 175, 80, 0.05);
}
`;
document.head.appendChild(styleSheet);

// Add Font Awesome if not already loaded
if (!document.querySelector('link[href*="font-awesome"]')) {
    const fontAwesome = document.createElement('link');
    fontAwesome.rel = 'stylesheet';
    fontAwesome.href = 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.3.0/css/all.min.css';
    document.head.appendChild(fontAwesome);
}
