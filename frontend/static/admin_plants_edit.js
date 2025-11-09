// Admin Plants Edit JavaScript

// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize the background particles
    initParticles();
    
    // Initialize the plant preview
    initPlantPreview();
    
    // Initialize form validations
    initFormValidation();
    
    // Show demo success message
    setTimeout(() => {
        showSuccessMessage('Plant edit mode ready!');
    }, 1500);
});

// Initialize floating background particles
function initParticles() {
    // Create particles container if it doesn't exist
    if (!document.querySelector('.plants-edit-particles-container')) {
        const container = document.createElement('div');
        container.className = 'plants-edit-particles-container';
        document.body.prepend(container);
    }
    
    const container = document.querySelector('.plants-edit-particles-container');
    
    // Create particles with random properties
    for (let i = 0; i < 8; i++) {
        createParticle(container);
    }
    
    // Add more particles every few seconds
    setInterval(() => {
        if (document.querySelectorAll('.plants-edit-particle').length < 15) {
            createParticle(container);
        }
    }, 3000);
}

// Create a single floating particle
function createParticle(container) {
    const particle = document.createElement('div');
    particle.className = 'plants-edit-particle';
    
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

// Initialize plant preview
function initPlantPreview() {
    const form = document.querySelector('.add-user-form');
    if (!form) return;
    
    // Create preview section
    const previewContainer = document.createElement('div');
    previewContainer.className = 'plant-preview';
    previewContainer.innerHTML = `
        <h3>Plant Preview</h3>
        <img src="" alt="Plant Preview" class="plant-preview-img" />
        <div class="plant-preview-details">
            <div class="plant-detail">
                <i class="fas fa-seedling"></i>
                <span class="preview-name">Plant Name</span>
            </div>
            <div class="plant-detail">
                <i class="fas fa-flask"></i>
                <span class="preview-scientific">Scientific Name</span>
            </div>
            <div class="plant-detail">
                <i class="fas fa-calendar-day"></i>
                <span class="preview-duration">Duration</span>
            </div>
            <div class="plant-detail">
                <i class="fas fa-leaf"></i>
                <span class="preview-type">Type</span>
            </div>
        </div>
        <p class="preview-description">Plant description will appear here...</p>
    `;
    
    // Insert at the beginning of the form
    form.prepend(previewContainer);
    
    // Update preview with initial values
    updatePreview();
    
    // Add event listeners to update preview as user types
    const nameInput = document.querySelector('input[name="name"]');
    const scientificInput = document.querySelector('input[name="scientific_name"]');
    const durationInput = document.querySelector('input[name="duration_days"]');
    const typeInput = document.querySelector('input[name="type"]');
    const photoInput = document.querySelector('input[name="photo_url"]');
    const descriptionInput = document.querySelector('textarea[name="description"]');
    
    if (nameInput) nameInput.addEventListener('input', updatePreview);
    if (scientificInput) scientificInput.addEventListener('input', updatePreview);
    if (durationInput) durationInput.addEventListener('input', updatePreview);
    if (typeInput) typeInput.addEventListener('input', updatePreview);
    if (photoInput) photoInput.addEventListener('input', updatePreview);
    if (descriptionInput) descriptionInput.addEventListener('input', updatePreview);
    
    // Add span elements with hints
    addFormHints();
}

// Update plant preview based on form inputs
function updatePreview() {
    const nameInput = document.querySelector('input[name="name"]');
    const scientificInput = document.querySelector('input[name="scientific_name"]');
    const durationInput = document.querySelector('input[name="duration_days"]');
    const typeInput = document.querySelector('input[name="type"]');
    const photoInput = document.querySelector('input[name="photo_url"]');
    const descriptionInput = document.querySelector('textarea[name="description"]');
    
    const previewImg = document.querySelector('.plant-preview-img');
    const previewName = document.querySelector('.preview-name');
    const previewScientific = document.querySelector('.preview-scientific');
    const previewDuration = document.querySelector('.preview-duration');
    const previewType = document.querySelector('.preview-type');
    const previewDescription = document.querySelector('.preview-description');
    
    if (previewImg && photoInput) {
        previewImg.src = photoInput.value || 'https://via.placeholder.com/180x180?text=Plant+Image';
        previewImg.onerror = function() {
            this.src = 'https://via.placeholder.com/180x180?text=Invalid+Image+URL';
        };
    }
    
    if (previewName && nameInput) {
        previewName.textContent = nameInput.value || 'Plant Name';
    }
    
    if (previewScientific && scientificInput) {
        previewScientific.textContent = scientificInput.value || 'Scientific Name';
    }
    
    if (previewDuration && durationInput) {
        previewDuration.textContent = durationInput.value ? `${durationInput.value} days` : 'Duration';
    }
    
    if (previewType && typeInput) {
        previewType.textContent = typeInput.value || 'Type';
    }
    
    if (previewDescription && descriptionInput) {
        previewDescription.textContent = descriptionInput.value || 'Plant description will appear here...';
        
        // Truncate if too long
        if (previewDescription.textContent.length > 100) {
            previewDescription.textContent = previewDescription.textContent.substring(0, 100) + '...';
        }
    }
}

// Add hints to the form fields
function addFormHints() {
    // Add additional information for the fields
    const formGroups = document.querySelectorAll('.form-group');
    
    formGroups.forEach(group => {
        const input = group.querySelector('input, textarea');
        if (!input) return;
        
        let hintText = '';
        
        switch (input.name) {
            case 'name':
                hintText = 'The common name of the plant';
                break;
            case 'scientific_name':
                hintText = 'Genus and species (Latin name)';
                break;
            case 'duration_days':
                hintText = 'How many days until harvest';
                break;
            case 'type':
                hintText = 'Category (e.g., vegetable, herb)';
                break;
            case 'photo_url':
                hintText = 'URL to an image of the plant';
                break;
            case 'description':
                hintText = 'Growing information and plant details';
                break;
        }
        
        if (hintText) {
            const hint = document.createElement('span');
            hint.className = 'form-hint';
            hint.textContent = hintText;
            hint.style.display = 'block';
            hint.style.fontSize = '0.8rem';
            hint.style.color = '#6c757d';
            hint.style.marginTop = '5px';
            group.appendChild(hint);
        }
    });
    
    // Set textarea to full width
    const textareaGroup = document.querySelector('textarea').closest('.form-group');
    if (textareaGroup) {
        textareaGroup.classList.add('full-width');
    }
    
    // Set URL preview to full width
    const urlGroup = document.querySelector('input[name="photo_url"]').closest('.form-group');
    if (urlGroup) {
        urlGroup.classList.add('full-width');
    }
    
    // Create form controls container for the button
    const submitButton = document.querySelector('button[type="submit"]');
    if (submitButton) {
        const formControls = document.createElement('div');
        formControls.className = 'form-controls';
        
        // Move submit button to the new container
        submitButton.parentElement.removeChild(submitButton);
        
        // Add icon to the button
        submitButton.innerHTML = '<i class="fas fa-save"></i> Save Changes';
        
        // Add a cancel button
        const cancelButton = document.createElement('button');
        cancelButton.type = 'button';
        cancelButton.className = 'btn btn-danger';
        cancelButton.innerHTML = '<i class="fas fa-times"></i> Cancel';
        cancelButton.addEventListener('click', function() {
            window.location.href = document.querySelector('a[href*="admin_plants"]').href;
        });
        
        formControls.appendChild(cancelButton);
        formControls.appendChild(submitButton);
        
        // Add the form controls to the form
        document.querySelector('.add-user-form').appendChild(formControls);
    }
}

// Form validation
function initFormValidation() {
    const form = document.querySelector('.add-user-form');
    if (!form) return;
    
    form.addEventListener('submit', function(e) {
        let isValid = true;
        
        // Validate name
        const nameInput = document.querySelector('input[name="name"]');
        if (nameInput.value.trim() === '') {
            showValidationError(nameInput, 'Plant name is required');
            isValid = false;
        } else {
            clearValidationError(nameInput);
        }
        
        // Validate scientific name
        const scientificInput = document.querySelector('input[name="scientific_name"]');
        if (scientificInput.value.trim() === '') {
            showValidationError(scientificInput, 'Scientific name is required');
            isValid = false;
        } else {
            clearValidationError(scientificInput);
        }
        
        // Validate duration
        const durationInput = document.querySelector('input[name="duration_days"]');
        if (durationInput.value < 1) {
            showValidationError(durationInput, 'Duration must be at least 1 day');
            isValid = false;
        } else {
            clearValidationError(durationInput);
        }
        
        // Validate photo URL
        const photoInput = document.querySelector('input[name="photo_url"]');
        if (photoInput.value.trim() === '' || !isValidUrl(photoInput.value)) {
            showValidationError(photoInput, 'Please enter a valid URL');
            isValid = false;
        } else {
            clearValidationError(photoInput);
        }
        
        // Validate description
        const descriptionInput = document.querySelector('textarea[name="description"]');
        if (descriptionInput.value.trim().length < 10) {
            showValidationError(descriptionInput, 'Description must be at least 10 characters');
            isValid = false;
        } else {
            clearValidationError(descriptionInput);
        }
        
        if (!isValid) {
            e.preventDefault();
        } else {
            showSuccessMessage('Saving plant changes...');
        }
    });
    
    // URL validation helper
    function isValidUrl(url) {
        try {
            new URL(url);
            return true;
        } catch {
            return false;
        }
    }
}

// Show validation error
function showValidationError(input, message) {
    const formGroup = input.closest('.form-group');
    
    // Remove any existing error
    const existingError = formGroup.querySelector('.validation-error');
    if (existingError) {
        existingError.remove();
    }
    
    // Create error message
    const errorElement = document.createElement('div');
    errorElement.className = 'validation-error';
    errorElement.textContent = message;
    errorElement.style.color = '#dc3545';
    errorElement.style.fontSize = '0.85rem';
    errorElement.style.marginTop = '5px';
    formGroup.appendChild(errorElement);
    
    // Highlight input
    input.style.borderColor = '#dc3545';
    input.style.backgroundColor = 'rgba(220, 53, 69, 0.05)';
    
    // Shake animation
    input.style.animation = 'shake 0.5s';
    setTimeout(() => {
        input.style.animation = '';
    }, 500);
}

// Clear validation error
function clearValidationError(input) {
    const formGroup = input.closest('.form-group');
    
    // Remove any existing error
    const existingError = formGroup.querySelector('.validation-error');
    if (existingError) {
        existingError.remove();
    }
    
    // Reset input styling
    input.style.borderColor = '';
    input.style.backgroundColor = '';
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
`;
document.head.appendChild(styleSheet);

// Add Font Awesome if not already loaded
if (!document.querySelector('link[href*="font-awesome"]')) {
    const fontAwesome = document.createElement('link');
    fontAwesome.rel = 'stylesheet';
    fontAwesome.href = 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.3.0/css/all.min.css';
    document.head.appendChild(fontAwesome);
}
