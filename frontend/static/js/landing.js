/**
 * AI-Garden Ultimate Landing Page
 * Advanced interactions, animations and effects
 */

// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', () => {
    // ===== Core Variables =====
    const BREAKPOINTS = {
        mobile: 480,
        tablet: 768,
        laptop: 1024,
        desktop: 1440
    };
    
    // Check for reduced motion preference
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    
    // ===== Helper Functions =====
    
    /**
     * Throttle function to limit execution rate
     */
    const throttle = (callback, delay = 100) => {
        let timeout = null;
        return (...args) => {
            if (!timeout) {
                timeout = setTimeout(() => {
                    callback(...args);
                    timeout = null;
                }, delay);
            }
        };
    };
    
    /**
     * Check if element is in viewport
     */
    const isInViewport = (element, offset = 0) => {
        const rect = element.getBoundingClientRect();
        return (
            rect.top <= (window.innerHeight || document.documentElement.clientHeight) - offset &&
            rect.bottom >= offset
        );
    };
    
    // ===== Video Background Logic =====
    const initVideoBackground = () => {
        // Create video container
        const videoContainer = document.createElement('div');
        videoContainer.classList.add('video-container');
        
        // Create video element
        const video = document.createElement('video');
        video.id = 'bg-video';
        video.classList.add('bg-video');
        video.autoplay = true;
        video.loop = true;
        video.muted = true;
        video.playsInline = true;
        video.setAttribute('aria-hidden', 'true');
        
        // Add sources for different formats with lazy loading
        const source1 = document.createElement('source');
        source1.src = './static/videos/garden-bg.mp4';
        source1.type = 'video/mp4';
        
        // Create overlay for better text visibility
        const overlay = document.createElement('div');
        overlay.classList.add('video-overlay');
        
        // Create video fallback
        const fallback = document.createElement('div');
        fallback.classList.add('video-fallback');
        
        // Add video controls
        const controls = document.createElement('div');
        controls.classList.add('video-controls');
        
        const playPauseBtn = document.createElement('button');
        playPauseBtn.id = 'video-toggle';
        playPauseBtn.classList.add('video-toggle');
        playPauseBtn.setAttribute('aria-label', 'Pause background video');
        playPauseBtn.innerHTML = '<span class="icon">❚❚</span>';
        
        // Build the structure
        controls.appendChild(playPauseBtn);
        video.appendChild(source1);
        videoContainer.appendChild(video);
        videoContainer.appendChild(overlay);
        videoContainer.appendChild(fallback);
        
        // Get the landing hero section
        const heroSection = document.querySelector('.landing-hero');
        
        if (heroSection) {
            // Insert video container at the beginning of hero section
            heroSection.insertBefore(videoContainer, heroSection.firstChild);
            // Add controls to the hero section
            heroSection.appendChild(controls);
            
            // Video control logic
            let isPlaying = true;
            playPauseBtn.addEventListener('click', () => {
                if (isPlaying) {
                    video.pause();
                    playPauseBtn.innerHTML = '<span class="icon">▶</span>';
                    playPauseBtn.setAttribute('aria-label', 'Play background video');
                } else {
                    video.play();
                    playPauseBtn.innerHTML = '<span class="icon">❚❚</span>';
                    playPauseBtn.setAttribute('aria-label', 'Pause background video');
                }
                isPlaying = !isPlaying;
            });
            
            // Check if we need to disable video for performance/accessibility
            if (prefersReducedMotion) {
                video.style.display = 'none';
                fallback.style.display = 'block';
                controls.style.display = 'none';
            }
        }
    };

    // ===== Custom Cursor =====
    const initCustomCursor = () => {
        if (prefersReducedMotion || window.innerWidth < BREAKPOINTS.tablet) {
            return; // Don't initialize on mobile or if reduced motion is preferred
        }
        
        // Create cursor elements
        const cursor = document.createElement('div');
        cursor.classList.add('custom-cursor');
        
        const cursorBorder = document.createElement('div');
        cursorBorder.classList.add('cursor-border');
        
        // Add to DOM
        document.body.appendChild(cursor);
        document.body.appendChild(cursorBorder);
        
        // Hide default cursor
        document.body.classList.add('custom-cursor-active');
        
        // Track cursor position
        const moveCursor = (e) => {
            const posX = e.clientX;
            const posY = e.clientY;
            
            // Move cursor dot instantly
            cursor.style.transform = `translate3d(${posX}px, ${posY}px, 0)`;
            
            // Move border with slight delay for trail effect
            requestAnimationFrame(() => {
                cursorBorder.style.transform = `translate3d(${posX}px, ${posY}px, 0)`;
            });
        };
        
        // Handle interactive elements
        const handleInteractiveElements = () => {
            const interactiveElements = document.querySelectorAll('a, button, .btn, .feature-card');
            
            interactiveElements.forEach(el => {
                el.addEventListener('mouseenter', () => {
                    cursor.classList.add('cursor-active');
                    cursorBorder.classList.add('border-active');
                });
                
                el.addEventListener('mouseleave', () => {
                    cursor.classList.remove('cursor-active');
                    cursorBorder.classList.remove('border-active');
                });
                
                // Add magnetic effect to buttons
                if (el.classList.contains('btn')) {
                    el.addEventListener('mousemove', (e) => {
                        const bounds = el.getBoundingClientRect();
                        const centerX = bounds.left + bounds.width / 2;
                        const centerY = bounds.top + bounds.height / 2;
                        
                        const distanceX = (e.clientX - centerX) * 0.2;
                        const distanceY = (e.clientY - centerY) * 0.2;
                        
                        el.style.transform = `translate3d(${distanceX}px, ${distanceY}px, 0)`;
                    });
                    
                    el.addEventListener('mouseleave', () => {
                        el.style.transform = '';
                    });
                }
            });
        };
        
        // Initialize cursor events
        document.addEventListener('mousemove', moveCursor);
        handleInteractiveElements();
        
        // Handle cursor going off screen
        document.addEventListener('mouseout', () => {
            cursor.style.opacity = '0';
            cursorBorder.style.opacity = '0';
        });
        
        document.addEventListener('mouseover', () => {
            cursor.style.opacity = '1';
            cursorBorder.style.opacity = '1';
        });
    };
    
    // ===== Parallax Effects =====
    const initParallaxEffects = () => {
        if (prefersReducedMotion) return;
        
        // Create parallax elements
        const createParallaxElements = () => {
            const container = document.querySelector('.landing-shell');
            if (!container) return;
            
            // Create decorative leaf elements
            const elements = 15; // Number of parallax elements
            const types = ['leaf', 'seed', 'flower'];
            
            for (let i = 0; i < elements; i++) {
                const element = document.createElement('div');
                const type = types[Math.floor(Math.random() * types.length)];
                const variant = Math.floor(Math.random() * 3) + 1;
                
                element.classList.add('parallax-element', `${type}-${variant}`);
                
                // Random position and size
                const posX = Math.random() * 100;
                const posY = Math.random() * 200;
                const size = Math.random() * 30 + 15;
                const rotation = Math.random() * 360;
                
                element.style.left = `${posX}%`;
                element.style.top = `${posY}vh`;
                element.style.width = `${size}px`;
                element.style.height = `${size}px`;
                element.style.transform = `rotate(${rotation}deg)`;
                element.style.opacity = Math.random() * 0.5 + 0.1;
                
                // Set z-index randomly between -1 and -10
                element.style.zIndex = -Math.floor(Math.random() * 10) - 1;
                
                // Add random animation delay
                element.style.animationDelay = `${Math.random() * 5}s`;
                
                container.appendChild(element);
            }
        };
        
        // Move elements on mouse move
        const moveParallaxElements = throttle((e) => {
            const elements = document.querySelectorAll('.parallax-element');
            if (!elements.length) return;
            
            const mouseX = e.clientX / window.innerWidth - 0.5;
            const mouseY = e.clientY / window.innerHeight - 0.5;
            
            elements.forEach((el, index) => {
                const depth = Math.random() * 20 + 5;
                const moveX = mouseX * depth;
                const moveY = mouseY * depth;
                
                // Use requestAnimationFrame for smooth animation
                requestAnimationFrame(() => {
                    el.style.transform = `translate3d(${moveX}px, ${moveY}px, 0) rotate(${el.dataset.rotation || 0}deg)`;
                });
            });
        }, 30);
        
        createParallaxElements();
        document.addEventListener('mousemove', moveParallaxElements);
    };
    
    // ===== Scroll Animations =====
    const initScrollAnimations = () => {
        // Create progress indicator
        const progressIndicator = document.createElement('div');
        progressIndicator.classList.add('scroll-progress');
        document.body.appendChild(progressIndicator);
        
        // Header scroll effect
        const header = document.querySelector('.landing-header');
        
        // Animate elements on scroll
        const handleScrollAnimations = throttle(() => {
            // Update progress bar
            const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
            const scrollHeight = document.documentElement.scrollHeight - document.documentElement.clientHeight;
            const progress = (scrollTop / scrollHeight) * 100;
            
            progressIndicator.style.width = `${progress}%`;
            
            // Header effect
            if (header) {
                if (scrollTop > 50) {
                    header.classList.add('scrolled');
                } else {
                    header.classList.remove('scrolled');
                }
            }
            
            // Animate elements when they enter viewport
            const animateElements = () => {
                // Feature cards with staggered animation
                document.querySelectorAll('.feature-card').forEach((card, index) => {
                    if (isInViewport(card, 100)) {
                        setTimeout(() => {
                            card.classList.add('animate-in');
                        }, index * 100); // Staggered delay
                    }
                });
                
                // Details items with alternate animation
                document.querySelectorAll('.detail-item').forEach((item, index) => {
                    if (isInViewport(item, 50)) {
                        setTimeout(() => {
                            item.classList.add(index % 2 === 0 ? 'slide-in-left' : 'slide-in-right');
                        }, index * 120);
                    }
                });
                
                // Section titles
                document.querySelectorAll('.section-title').forEach(title => {
                    if (isInViewport(title, 100)) {
                        title.classList.add('reveal');
                    }
                });
            };
            
            animateElements();
            
            // Parallax scrolling for sections
            const sections = document.querySelectorAll('.project-overview, .feature-grid, .ai-details');
            sections.forEach(section => {
                if (isInViewport(section)) {
                    const scrollPosition = window.pageYOffset;
                    const sectionSpeed = section.dataset.speed || 0.1;
                    const yPos = -(scrollPosition * sectionSpeed);
                    section.style.backgroundPositionY = yPos + 'px';
                }
            });
        }, 50);
        
        // Initialize scroll animations
        window.addEventListener('scroll', handleScrollAnimations);
        // Run once to set initial states
        setTimeout(handleScrollAnimations, 100);
    };

    // ===== Hero Text Animation =====
    const initHeroAnimation = () => {
        const heroTitle = document.querySelector('.hero-title');
        const heroSubtitle = document.querySelector('.hero-subtitle');
        const ctaRow = document.querySelector('.cta-row');
        
        if (!heroTitle || !heroSubtitle || !ctaRow) return;
        
        // Add animation classes
        heroTitle.classList.add('animate-title');
        heroSubtitle.classList.add('animate-subtitle');
        ctaRow.classList.add('animate-cta');
        
        // Text splitting for word-by-word animation if not reduced motion
        if (!prefersReducedMotion) {
            // For title
            const titleText = heroTitle.textContent;
            heroTitle.textContent = '';
            
            titleText.split(' ').forEach((word, index) => {
                const wordSpan = document.createElement('span');
                wordSpan.classList.add('title-word');
                wordSpan.style.animationDelay = `${0.2 + index * 0.15}s`;
                wordSpan.textContent = word + ' ';
                heroTitle.appendChild(wordSpan);
            });
        }
    };

    // ===== Button Interaction Effects =====
    const initButtonEffects = () => {
        document.querySelectorAll('.btn').forEach(button => {
            // Add ripple effect on click
            button.addEventListener('click', function(e) {
                if (prefersReducedMotion) return;
                
                const x = e.clientX - this.getBoundingClientRect().left;
                const y = e.clientY - this.getBoundingClientRect().top;
                
                const ripple = document.createElement('span');
                ripple.classList.add('btn-ripple');
                ripple.style.left = `${x}px`;
                ripple.style.top = `${y}px`;
                
                this.appendChild(ripple);
                
                setTimeout(() => {
                    ripple.remove();
                }, 600);
            });
        });
    };
    
    // ===== Loading Animation =====
    const initLoading = () => {
        // Create loading overlay
        const loader = document.createElement('div');
        loader.classList.add('page-loader');
        loader.innerHTML = `
            <div class="loader-content">
                <div class="loader-icon">
                    <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
                        <path class="leaf" d="M50,90 C10,90 10,10 50,10 C90,10 90,50 50,50 C10,50 10,90 50,90 Z" />
                    </svg>
                </div>
                <div class="loader-text">Growing AI-Garden</div>
            </div>
        `;
        document.body.appendChild(loader);
        
        // Hide loader after content loads
        window.addEventListener('load', () => {
            setTimeout(() => {
                loader.classList.add('loader-hidden');
                setTimeout(() => {
                    loader.remove();
                }, 500);
            }, 500);
        });
        
        // Fallback if load event doesn't fire
        setTimeout(() => {
            if (document.body.contains(loader)) {
                loader.classList.add('loader-hidden');
                setTimeout(() => {
                    loader.remove();
                }, 500);
            }
        }, 3000);
    };

    // ===== Initialize Components =====
    // Load only if not in reduced motion mode or selectively
    initLoading();
    initHeroAnimation();
    initButtonEffects();
    initVideoBackground();
    initScrollAnimations();
    
    if (!prefersReducedMotion) {
        initCustomCursor();
        initParallaxEffects();
    }
    
    // ===== Accessibility Features =====
    const initAccessibility = () => {
        // Add skip to content link for keyboard users
        const skipLink = document.createElement('a');
        skipLink.href = '#main-content';
        skipLink.classList.add('skip-link');
        skipLink.textContent = 'Skip to content';
        document.body.insertBefore(skipLink, document.body.firstChild);
        
        // Add ID to main content
        const mainContent = document.querySelector('.landing-hero');
        if (mainContent) {
            mainContent.id = 'main-content';
            mainContent.setAttribute('tabindex', '-1');
        }
        
        // Make all interactive elements focusable
        document.querySelectorAll('.feature-card').forEach(card => {
            card.setAttribute('tabindex', '0');
        });
        
        // Listen for keyboard events on interactive elements
        document.querySelectorAll('.feature-card, .btn').forEach(element => {
            element.addEventListener('keydown', (e) => {
                // Add keyboard interaction for Enter/Space
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    element.click();
                }
            });
        });
    };
    
    initAccessibility();
});
