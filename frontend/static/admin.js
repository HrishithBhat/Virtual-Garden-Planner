// Admin Dashboard JavaScript

// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize the background particles
    initParticles();
    
    // Initialize animated elements
    initAnimations();
    
    // Initialize the user table and filters
    initUserTable();
    
    // Initialize form validations and interactions
    initFormInteractions();
    
    // Show a demo success message
    setTimeout(() => {
        showSuccessMessage('Welcome to the enhanced admin dashboard!');
    }, 1500);
});

// Initialize floating background particles
function initParticles() {
    const container = document.querySelector('.admin-particles-container');
    if (!container) return;
    
    // Create 15 particles with random properties
    for (let i = 0; i < 15; i++) {
        createParticle(container);
    }
    
    // Add more particles every few seconds
    setInterval(() => {
        if (document.querySelectorAll('.admin-particle').length < 20) {
            createParticle(container);
        }
    }, 3000);
}

// Create a single floating particle
function createParticle(container) {
    const particle = document.createElement('div');
    particle.className = 'admin-particle';
    
    // Random size between 20 and 80px
    const size = Math.random() * 60 + 20;
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
    // Animate table rows with delay
    const tableRows = document.querySelectorAll('.table-row-animated');
    tableRows.forEach((row, index) => {
        row.style.animationDelay = `${0.1 + index * 0.1}s`;
    });
}

// Initialize user table with search and filtering
function initUserTable() {
    const searchInput = document.getElementById('userSearch');
    const filterButtons = document.querySelectorAll('.filter-btn');
    const tableRows = document.querySelectorAll('.users-table tbody tr');
    
    if (!searchInput) return;
    // Initial render to ensure correct state
    filterTable('', getCurrentFilter());
    
    // Search functionality
    searchInput.addEventListener('input', function() {
        const searchTerm = this.value.toLowerCase();
        filterTable(searchTerm, getCurrentFilter());
    });
    
    // Filter buttons
    filterButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            // Remove active class from all buttons
            filterButtons.forEach(b => b.classList.remove('active'));
            // Add active class to clicked button
            this.classList.add('active');

            // Filter the table
            filterTable(searchInput.value.toLowerCase(), this.dataset.role || 'all');
        });
    });
    
    // Get current selected filter
    function getCurrentFilter() {
        const activeBtn = document.querySelector('.filter-btn.active');
        return activeBtn && activeBtn.dataset && activeBtn.dataset.role ? activeBtn.dataset.role : 'all';
    }
    
    // Filter table based on search term and role filter
    function filterTable(searchTerm, roleFilter) {
        const filter = (roleFilter || 'all').toLowerCase();
        tableRows.forEach(row => {
            const usernameEl = row.querySelector('.username');
            const username = usernameEl ? usernameEl.textContent.toLowerCase() : '';
            const emailCell = row.querySelector('td:nth-child(3)');
            const email = emailCell ? emailCell.textContent.toLowerCase() : '';
            const roleBadge = row.querySelector('.user-role-badge[data-role]') || row.querySelector('.user-role-badge');
            const roleValue = roleBadge ? (roleBadge.dataset.role || roleBadge.textContent.trim().toLowerCase()) : '';

            const matchesSearch = (!searchTerm || username.includes(searchTerm) || email.includes(searchTerm));
            const matchesFilter = roleMatchesFilter(roleValue, filter);

            if (matchesSearch && matchesFilter) {
                row.style.display = '';
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

    function roleMatchesFilter(roleValue, filter) {
        if (!filter || filter === 'all') return true;
        if (!roleValue) return false;
        const normalizedRole = roleValue.trim().toLowerCase();
        if (filter === 'sub_admin') {
            return normalizedRole === 'sub_admin' || normalizedRole.endsWith('_sub_admin');
        }
        if (filter === 'user') {
            return normalizedRole === 'user';
        }
        return normalizedRole === filter;
    }
    
    // Check if any rows are visible and toggle the no results message
    function toggleNoResultsMessage() {
        const visibleRows = Array.from(tableRows).filter(row => row.style.display !== 'none');
        const noDataRow = document.querySelector('.no-data-row');

        if (visibleRows.length === 0) {
            if (!noDataRow) {
                const tbody = document.querySelector('.users-table tbody');
                const tr = document.createElement('tr');
                tr.className = 'no-data-row';
                tr.innerHTML = `
                    <td colspan="6" class="no-data-cell">
                        <div class="no-data-message">
                            <i class="fas fa-search"></i>
                            <p>No users match your search criteria</p>
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
function initFormInteractions() {
    // Password toggle
    const passwordToggles = document.querySelectorAll('.password-toggle');
    passwordToggles.forEach(toggle => {
        toggle.addEventListener('click', function() {
            const input = this.previousElementSibling;
            const type = input.getAttribute('type');
            
            if (type === 'password') {
                input.setAttribute('type', 'text');
                this.innerHTML = '<i class="fas fa-eye-slash"></i>';
            } else {
                input.setAttribute('type', 'password');
                this.innerHTML = '<i class="fas fa-eye"></i>';
            }
        });
    });
    
    // Password strength meter
    const passwordInput = document.getElementById('userPassword');
    if (passwordInput) {
        passwordInput.addEventListener('input', function() {
            const strengthBar = document.querySelector('.strength-bar');
            const value = this.value;
            
            // Calculate password strength
            let strength = 0;
            
            // Length check
            if (value.length >= 8) strength += 25;
            
            // Contains lowercase letters
            if (value.match(/[a-z]+/)) strength += 25;
            
            // Contains uppercase letters
            if (value.match(/[A-Z]+/)) strength += 25;
            
            // Contains numbers or special characters
            if (value.match(/[0-9]+/) || value.match(/[$@#&!]+/)) strength += 25;
            
            // Update strength bar
            strengthBar.style.width = `${strength}%`;
            
            // Change color based on strength
            if (strength < 50) {
                strengthBar.style.background = '#e74c3c';
            } else if (strength < 75) {
                strengthBar.style.background = '#f39c12';
            } else {
                strengthBar.style.background = '#2ecc71';
            }
        });
    }
    
    // Form validation
    const addUserForm = document.getElementById('addUserForm');
    if (addUserForm) {
        addUserForm.addEventListener('submit', function(e) {
            // Let us validate first
            e.preventDefault();

            const username = document.getElementById('userName');
            const email = document.getElementById('userEmail');
            const password = document.getElementById('userPassword');
            const role = document.getElementById('userRole');

            let isValid = true;

            if (username.value.trim().length < 3) {
                showValidationError(username, 'Username must be at least 3 characters');
                isValid = false;
            } else {
                clearValidationError(username);
            }

            if (!isValidEmail(email.value)) {
                showValidationError(email, 'Please enter a valid email address');
                isValid = false;
            } else {
                clearValidationError(email);
            }

            if (password.value.length < 8) {
                showValidationError(password, 'Password must be at least 8 characters');
                isValid = false;
            } else {
                clearValidationError(password);
            }

            if (isValid) {
                // Submit to backend so the user is persisted and appears in Existing Users
                this.submit();
            }
        });
    }
    
    // Email validation helper
    function isValidEmail(email) {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
    }
    
    // Show validation error
    function showValidationError(input, message) {
        const formGroup = input.closest('.animated-form-group');
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
        const formGroup = input.closest('.animated-form-group');
        const errorMessage = formGroup.querySelector('.validation-message');
        
        if (errorMessage) {
            errorMessage.textContent = '';
        }
        
        input.style.borderColor = '';
    }
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
