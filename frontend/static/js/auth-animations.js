/**
 * auth-animations.js
 * Advanced animations and interactions for AI Garden authentication pages
 */

document.addEventListener('DOMContentLoaded', () => {
    // Initialize 3D tilt effect for the form container
    initTiltEffect();
    
    // Initialize floating labels
    initFloatingLabels();
    
    // Initialize magnetic buttons
    initMagneticButtons();
    
    // Initialize form animations
    initFormAnimations();
    
    // Initialize particles
    initParticles();
    
    // Initialize password strength visualizer
    initPasswordStrength();
    
    // Initialize advanced input validations
    initInputValidations();
    
    // Initialize container entrance animation
    animateContainerEntrance();
});

/**
 * Initialize 3D tilt effect for the form container
 */
function initTiltEffect() {
    const formContainer = document.querySelector('.form-container');
    if (!formContainer) return;
    
    formContainer.addEventListener('mousemove', (e) => {
        const rect = formContainer.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        
        const centerX = rect.width / 2;
        const centerY = rect.height / 2;
        
        const tiltX = (y - centerY) / 15;
        const tiltY = (centerX - x) / 15;
        
        formContainer.style.transform = `perspective(1000px) rotateX(${tiltX}deg) rotateY(${tiltY}deg)`;
    });
    
    formContainer.addEventListener('mouseleave', () => {
        formContainer.style.transform = 'perspective(1000px) rotateX(0) rotateY(0)';
    });
}

/**
 * Initialize floating label animations
 */
function initFloatingLabels() {
    const inputFields = document.querySelectorAll('.form-group input');
    
    inputFields.forEach(input => {
        // Create floating label if it doesn't exist
        if (!input.nextElementSibling || !input.nextElementSibling.classList.contains('floating-label')) {
            const placeholder = input.getAttribute('placeholder');
            if (placeholder) {
                const label = document.createElement('span');
                label.classList.add('floating-label');
                label.textContent = placeholder;
                input.parentNode.insertBefore(label, input.nextSibling);
                
                // Show the label immediately if the field has a value
                if (input.value !== '') {
                    label.classList.add('active');
                }
            }
        }
        
        // Add event listeners
        input.addEventListener('focus', function() {
            const label = this.nextElementSibling;
            if (label && label.classList.contains('floating-label')) {
                label.classList.add('active');
            }
        });
        
        input.addEventListener('blur', function() {
            const label = this.nextElementSibling;
            if (label && label.classList.contains('floating-label') && this.value === '') {
                label.classList.remove('active');
            }
        });
    });
}

/**
 * Initialize magnetic button effect
 */
function initMagneticButtons() {
    document.querySelectorAll('.btn-magnetic').forEach(button => {
        button.addEventListener('mousemove', (e) => {
            const rect = button.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            
            const centerX = rect.width / 2;
            const centerY = rect.height / 2;
            
            const distanceX = x - centerX;
            const distanceY = y - centerY;
            
            const magneticPull = 8; // Higher number = less movement
            
            button.style.transform = `translate(${distanceX / magneticPull}px, ${distanceY / magneticPull}px)`;
        });
        
        button.addEventListener('mouseleave', () => {
            button.style.transform = 'translate(0, 0)';
        });
    });
}

/**
 * Initialize form field animations
 */
function initFormAnimations() {
    // Add staggered animation to form groups
    const formGroups = document.querySelectorAll('.form-group');
    formGroups.forEach((group, index) => {
        group.style.opacity = '0';
        group.style.transform = 'translateY(20px)';
        
        setTimeout(() => {
            group.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
            group.style.opacity = '1';
            group.style.transform = 'translateY(0)';
        }, 300 + (index * 150));
    });
    
    // Animate submit button
    const submitBtn = document.querySelector('button[type="submit"]');
    if (submitBtn) {
        submitBtn.style.opacity = '0';
        submitBtn.style.transform = 'translateY(20px)';
        
        setTimeout(() => {
            submitBtn.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
            submitBtn.style.opacity = '1';
            submitBtn.style.transform = 'translateY(0)';
        }, 300 + (formGroups.length * 150));
    }
    
    // Add ripple effect to buttons
    document.querySelectorAll('.btn').forEach(button => {
        button.addEventListener('click', function(e) {
            const rect = button.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            
            const ripple = document.createElement('span');
            ripple.className = 'ripple';
            ripple.style.left = `${x}px`;
            ripple.style.top = `${y}px`;
            
            button.appendChild(ripple);
            
            setTimeout(() => {
                ripple.remove();
            }, 1000);
        });
    });
}

/**
 * Initialize background particles with advanced behavior
 */
function initParticles() {
    const particleContainer = document.querySelector('.particle-container');
    if (!particleContainer) return;
    
    const particleCount = 30;
    
    // Create initial batch of particles
    for (let i = 0; i < particleCount; i++) {
        createParticle(particleContainer);
    }
    
    // Create new particles at intervals for continuous effect
    setInterval(() => {
        createParticle(particleContainer);
    }, 1000);
    
    // Add interactive particles that follow mouse movement
    document.addEventListener('mousemove', (e) => {
        if (Math.random() > 0.92) { // Throttle creation to not overwhelm
            const mouseParticle = document.createElement('div');
            mouseParticle.classList.add('particle');
            
            const size = Math.random() * 4 + 2;
            mouseParticle.style.width = `${size}px`;
            mouseParticle.style.height = `${size}px`;
            mouseParticle.style.left = `${e.clientX}px`;
            mouseParticle.style.top = `${e.clientY}px`;
            
            // Custom animation for mouse particles
            mouseParticle.style.opacity = '0.6';
            mouseParticle.style.transform = 'scale(1)';
            mouseParticle.style.transition = 'all 1s ease-out';
            
            particleContainer.appendChild(mouseParticle);
            
            // Animate and remove
            setTimeout(() => {
                mouseParticle.style.opacity = '0';
                mouseParticle.style.transform = 'scale(0.2)';
                
                setTimeout(() => {
                    mouseParticle.remove();
                }, 1000);
            }, 10);
        }
    });
}

/**
 * Create a single particle with randomized properties
 */
function createParticle(container) {
    const particle = document.createElement('div');
    particle.classList.add('particle');
    
    // Randomize particle properties
    const size = Math.random() * 8 + 2;
    const posX = Math.random() * 100;
    const startY = 110 + Math.random() * 20; // Start below screen
    const duration = Math.random() * 20 + 15;
    const delay = Math.random() * 5;
    
    particle.style.width = `${size}px`;
    particle.style.height = `${size}px`;
    particle.style.left = `${posX}%`;
    particle.style.bottom = `-${startY}%`; // Start from bottom
    particle.style.opacity = '0';
    
    // Custom animation for upward floating
    const keyframes = [
        { opacity: 0, transform: 'translateY(0) scale(1)', offset: 0 },
        { opacity: 0.6, transform: 'translateY(-100px) scale(1.1)', offset: 0.1 },
        { opacity: 0.6, transform: 'translateY(-300px) translateX(50px) scale(0.9)', offset: 0.5 },
        { opacity: 0.4, transform: 'translateY(-600px) translateX(100px) scale(0.7)', offset: 0.8 },
        { opacity: 0, transform: 'translateY(-800px) translateX(150px) scale(0.5)', offset: 1 }
    ];
    
    const options = {
        duration: duration * 1000,
        delay: delay * 1000,
        fill: 'forwards',
        easing: 'cubic-bezier(0.4, 0, 0.2, 1)'
    };
    
    container.appendChild(particle);
    
    // Start animation after a brief delay
    setTimeout(() => {
        particle.animate(keyframes, options);
        
        // Remove particle after animation completes
        setTimeout(() => {
            particle.remove();
        }, duration * 1000 + delay * 1000);
    }, 10);
}

/**
 * Show success message with animation
 */
function showSuccessMessage(message) {
    // Remove any existing success message
    const existingMessage = document.querySelector('.success-message');
    if (existingMessage) {
        existingMessage.remove();
    }
    
    // Create new success message
    const successMessage = document.createElement('div');
    successMessage.classList.add('success-message');
    successMessage.textContent = message;
    
    // Add to document
    document.body.appendChild(successMessage);
    
    // Animate in
    setTimeout(() => {
        successMessage.classList.add('show');
    }, 10);
    
    // Remove after delay
    setTimeout(() => {
        successMessage.classList.remove('show');
        setTimeout(() => {
            successMessage.remove();
        }, 500);
    }, 5000);
}

/**
 * Show error message with animation
 * Note: This complements the server-side error display
 */
function showErrorMessage(message) {
    // Check for existing error container
    let errorContainer = document.querySelector('.error');
    
    // If none exists, create one
    if (!errorContainer) {
        errorContainer = document.createElement('div');
        errorContainer.classList.add('error');
        
        // Insert after subtitle
        const subtitle = document.querySelector('.page-subtitle');
        if (subtitle && subtitle.parentNode) {
            subtitle.parentNode.insertBefore(errorContainer, subtitle.nextSibling);
        } else {
            // Fallback to before the form
            const form = document.querySelector('form');
            if (form && form.parentNode) {
                form.parentNode.insertBefore(errorContainer, form);
            }
        }
    }
    
    // Add shake animation
    errorContainer.textContent = message;
    errorContainer.classList.add('shake');
    
    // Remove shake class after animation completes
    setTimeout(() => {
        errorContainer.classList.remove('shake');
    }, 500);
}

/**
 * Initialize password strength visualizer
 */
function initPasswordStrength() {
    const passwordInput = document.querySelector('input[type="password"]');
    if (!passwordInput) return;
    
    // Add strength indicator if it doesn't exist
    let strengthContainer = passwordInput.parentNode.querySelector('.password-strength');
    if (!strengthContainer) {
        strengthContainer = document.createElement('div');
        strengthContainer.className = 'password-strength';
        
        const meter = document.createElement('div');
        meter.className = 'password-strength-meter';
        strengthContainer.appendChild(meter);
        
        const text = document.createElement('div');
        text.className = 'password-strength-text';
        strengthContainer.appendChild(text);
        
        // Insert after password field
        passwordInput.parentNode.appendChild(strengthContainer);
    }
    
    // Add event listener to password input
    passwordInput.addEventListener('input', () => {
        updatePasswordStrength(passwordInput, strengthContainer);
    });
    
    // Initialize requirements list
    createPasswordRequirements(passwordInput);
    
    // Show requirements on focus
    passwordInput.addEventListener('focus', () => {
        const reqContainer = document.querySelector('.password-requirements');
        if (reqContainer) {
            reqContainer.classList.add('show');
        }
    });
    
    // Hide requirements on blur
    passwordInput.addEventListener('blur', () => {
        const reqContainer = document.querySelector('.password-requirements');
        if (reqContainer) {
            reqContainer.classList.remove('show');
        }
    });
}

/**
 * Update password strength meter and text
 */
function updatePasswordStrength(input, container) {
    const password = input.value;
    const meter = container.querySelector('.password-strength-meter');
    const text = container.querySelector('.password-strength-text');
    
    // Calculate strength score
    let strength = 0;
    
    // Check password length
    if (password.length >= 6) strength += 20;
    if (password.length >= 10) strength += 10;
    
    // Check for different character types
    if (/[A-Z]/.test(password)) strength += 20;
    if (/[a-z]/.test(password)) strength += 15;
    if (/[0-9]/.test(password)) strength += 20;
    if (/[^A-Za-z0-9]/.test(password)) strength += 25;
    
    // Update visual indicators
    meter.style.width = `${strength}%`;
    
    // Update strength class and text
    if (strength < 40) {
        container.className = 'password-strength weak';
        text.textContent = 'Weak password';
    } else if (strength < 70) {
        container.className = 'password-strength medium';
        text.textContent = 'Medium strength';
    } else {
        container.className = 'password-strength strong';
        text.textContent = 'Strong password';
    }
    
    // Update requirement indicators
    updatePasswordRequirements(password);
}

/**
 * Create password requirements list
 */
function createPasswordRequirements(passwordInput) {
    // Create container if it doesn't exist
    let reqContainer = document.querySelector('.password-requirements');
    if (!reqContainer) {
        reqContainer = document.createElement('div');
        reqContainer.className = 'password-requirements';
        
        const requirements = [
            { id: 'req-length', text: 'At least 6 characters', test: (p) => p.length >= 6 },
            { id: 'req-uppercase', text: 'At least one uppercase letter', test: (p) => /[A-Z]/.test(p) },
            { id: 'req-lowercase', text: 'At least one lowercase letter', test: (p) => /[a-z]/.test(p) },
            { id: 'req-number', text: 'At least one number', test: (p) => /[0-9]/.test(p) },
            { id: 'req-special', text: 'At least one special character', test: (p) => /[^A-Za-z0-9]/.test(p) }
        ];
        
        requirements.forEach(req => {
            const reqEl = document.createElement('div');
            reqEl.className = 'requirement unmet';
            reqEl.id = req.id;
            
            reqEl.innerHTML = `
                <i class="fas fa-circle"></i>
                <span>${req.text}</span>
            `;
            
            reqContainer.appendChild(reqEl);
        });
        
        // Insert after password strength indicator
        const strengthContainer = document.querySelector('.password-strength');
        if (strengthContainer) {
            strengthContainer.parentNode.insertBefore(reqContainer, strengthContainer.nextSibling);
        } else {
            passwordInput.parentNode.appendChild(reqContainer);
        }
    }
}

/**
 * Update password requirement indicators
 */
function updatePasswordRequirements(password) {
    const requirements = [
        { id: 'req-length', test: (p) => p.length >= 6 },
        { id: 'req-uppercase', test: (p) => /[A-Z]/.test(p) },
        { id: 'req-lowercase', test: (p) => /[a-z]/.test(p) },
        { id: 'req-number', test: (p) => /[0-9]/.test(p) },
        { id: 'req-special', test: (p) => /[^A-Za-z0-9]/.test(p) }
    ];
    
    requirements.forEach(req => {
        const reqEl = document.getElementById(req.id);
        if (!reqEl) return;
        
        const icon = reqEl.querySelector('i');
        
        if (req.test(password)) {
            reqEl.className = 'requirement met';
            icon.className = 'fas fa-check-circle';
        } else {
            reqEl.className = 'requirement unmet';
            icon.className = 'fas fa-circle';
        }
    });
}

/**
 * Initialize real-time input validations
 */
function initInputValidations() {
    // Username validation
    const usernameInput = document.querySelector('input[name="username"]');
    if (usernameInput) {
        usernameInput.addEventListener('input', debounce(function() {
            validateInput(usernameInput, value => {
                if (value.length < 3) return { valid: false, message: 'Username must be at least 3 characters' };
                if (!/^[a-zA-Z0-9_]+$/.test(value)) return { valid: false, message: 'Only letters, numbers and underscore allowed' };
                return { valid: true };
            });
        }, 500));
    }
    
    // Email validation
    const emailInput = document.querySelector('input[type="email"]');
    if (emailInput) {
        emailInput.addEventListener('input', debounce(function() {
            validateInput(emailInput, value => {
                if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) return { valid: false, message: 'Please enter a valid email address' };
                return { valid: true };
            });
        }, 500));
    }
}

/**
 * Validate an input field with custom validation function
 */
function validateInput(input, validationFn) {
    const value = input.value.trim();
    const result = validationFn(value);
    
    // Find or create validation indicator
    let indicator = input.parentNode.querySelector('.validation-indicator');
    if (!indicator) {
        indicator = document.createElement('span');
        indicator.className = 'validation-indicator';
        input.parentNode.querySelector('.field-validation')?.appendChild(indicator);
    }
    
    if (value === '') {
        indicator.className = 'validation-indicator';
        indicator.innerHTML = '';
        input.setCustomValidity('');
        return;
    }
    
    if (result.valid) {
        indicator.className = 'validation-indicator valid';
        indicator.innerHTML = '<i class="fas fa-check-circle"></i>';
        input.setCustomValidity('');
    } else {
        indicator.className = 'validation-indicator invalid';
        indicator.innerHTML = '<i class="fas fa-exclamation-circle"></i>';
        input.setCustomValidity(result.message || 'Invalid input');
        
        // Show tooltip with message
        if (result.message) {
            indicator.setAttribute('title', result.message);
        }
    }
}

/**
 * Debounce function to limit how often a function is called
 */
function debounce(func, wait) {
    let timeout;
    return function(...args) {
        const context = this;
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(context, args), wait);
    };
}

/**
 * Animate the container entrance
 */
function animateContainerEntrance() {
    const container = document.querySelector('.container');
    if (!container) return;
    
    // Start with reduced opacity
    container.style.opacity = '0';
    container.style.transform = 'translateY(30px) scale(0.95)';
    
    // Animate in after a short delay
    setTimeout(() => {
        container.style.transition = 'opacity 1s ease-out, transform 1s cubic-bezier(0.175, 0.885, 0.32, 1.275)';
        container.style.opacity = '1';
        container.style.transform = 'translateY(0) scale(1)';
    }, 200);
}
