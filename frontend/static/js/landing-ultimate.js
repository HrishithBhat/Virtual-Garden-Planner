/**
 * landing-ultimate.js
 * Advanced animations and interactions for the Ultimate AI Garden Landing Page
 */

document.addEventListener('DOMContentLoaded', () => {
  // Initialize intersection observers for animations
  initScrollAnimations();
  
  // Initialize particle system
  initParticles();
  
  // Initialize hover effects
  initHoverEffects();
  
  // Initialize video background
  initVideoBackground();
  
  // Initialize interactive elements
  initInteractiveElements();
});

/**
 * Initialize animations triggered by scrolling into view
 */
function initScrollAnimations() {
  // Create observer for fade-in animations
  const fadeObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          // Only trigger once for performance
          if (entry.target.dataset.once !== 'false') {
            fadeObserver.unobserve(entry.target);
          }
        } else if (entry.target.dataset.once === 'false') {
          entry.target.classList.remove('visible');
        }
      });
    },
    { threshold: 0.15 }
  );
  
  // Apply to all fade-in elements
  document.querySelectorAll('.fade-in').forEach(el => {
    fadeObserver.observe(el);
  });
  
  // Create observer for staggered animations
  const staggerObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const children = entry.target.querySelectorAll('.stagger-item');
          children.forEach((child, index) => {
            setTimeout(() => {
              child.classList.add('visible');
            }, 100 * index);
          });
          staggerObserver.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.1 }
  );
  
  // Apply to all stagger containers
  document.querySelectorAll('.stagger-container').forEach(el => {
    staggerObserver.observe(el);
  });
  
  // Create observer for parallax effects
  const parallaxObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          initParallax(entry.target);
        }
      });
    },
    { threshold: 0 }
  );
  
  // Apply to all parallax elements
  document.querySelectorAll('.parallax').forEach(el => {
    parallaxObserver.observe(el);
  });
}

/**
 * Initialize parallax effect for an element
 */
function initParallax(element) {
  const speed = element.dataset.speed || 0.2;
  
  window.addEventListener('scroll', () => {
    const scrollPosition = window.pageYOffset;
    const elementOffset = element.offsetTop;
    const distance = (scrollPosition - elementOffset) * speed;
    
    if (element.classList.contains('parallax-bg')) {
      element.style.backgroundPositionY = `${distance}px`;
    } else {
      element.style.transform = `translateY(${distance}px)`;
    }
  });
}

/**
 * Initialize particle system for background
 */
function initParticles() {
  const particleContainer = document.querySelector('.particle-container');
  if (!particleContainer) return;
  
  const particleCount = 30;
  
  for (let i = 0; i < particleCount; i++) {
    const particle = document.createElement('div');
    particle.classList.add('particle');
    
    // Randomize particle properties
    const size = Math.random() * 8 + 3;
    const posX = Math.random() * 100;
    const posY = Math.random() * 100;
    const duration = Math.random() * 20 + 10;
    const delay = Math.random() * 5;
    
    particle.style.width = `${size}px`;
    particle.style.height = `${size}px`;
    particle.style.left = `${posX}%`;
    particle.style.top = `${posY}%`;
    particle.style.animationDuration = `${duration}s`;
    particle.style.animationDelay = `${delay}s`;
    
    particleContainer.appendChild(particle);
  }
}

/**
 * Initialize hover effects for interactive elements
 */
function initHoverEffects() {
  // Magnetic effect for buttons
  document.querySelectorAll('.btn-magnetic').forEach(button => {
    button.addEventListener('mousemove', (e) => {
      const rect = button.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      
      const centerX = rect.width / 2;
      const centerY = rect.height / 2;
      
      const distanceX = x - centerX;
      const distanceY = y - centerY;
      
      const magneticPull = 10;
      
      button.style.transform = `translate(${distanceX / magneticPull}px, ${distanceY / magneticPull}px)`;
    });
    
    button.addEventListener('mouseleave', () => {
      button.style.transform = 'translate(0, 0)';
    });
  });
  
  // Floating effect for feature cards
  document.querySelectorAll('.feature-card').forEach(card => {
    card.addEventListener('mousemove', (e) => {
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      
      const centerX = rect.width / 2;
      const centerY = rect.height / 2;
      
      const tiltX = (y - centerY) / 10;
      const tiltY = (centerX - x) / 10;
      
      card.style.transform = `perspective(1000px) rotateX(${tiltX}deg) rotateY(${tiltY}deg)`;
    });
    
    card.addEventListener('mouseleave', () => {
      card.style.transform = 'perspective(1000px) rotateX(0) rotateY(0)';
    });
  });
}

/**
 * Initialize video background with fallback
 */
function initVideoBackground() {
  const videoContainer = document.querySelector('.video-background');
  if (!videoContainer) return;
  
  const video = videoContainer.querySelector('video');
  if (!video) return;
  
  // Check if video can play, otherwise show fallback
  video.addEventListener('error', () => {
    videoContainer.classList.add('video-fallback');
  });
  
  // Add pause/play functionality
  const toggleBtn = document.querySelector('.video-toggle');
  if (toggleBtn) {
    toggleBtn.addEventListener('click', () => {
      if (video.paused) {
        video.play();
        toggleBtn.textContent = 'Pause';
      } else {
        video.pause();
        toggleBtn.textContent = 'Play';
      }
    });
  }
  
  // Add mute/unmute functionality
  const muteBtn = document.querySelector('.video-mute');
  if (muteBtn) {
    muteBtn.addEventListener('click', () => {
      video.muted = !video.muted;
      muteBtn.textContent = video.muted ? 'Unmute' : 'Mute';
    });
  }
}

/**
 * Initialize interactive elements like carousel, tabs, etc.
 */
function initInteractiveElements() {
  // Initialize image carousel
  initCarousel();
  
  // Initialize tabs
  initTabs();
  
  // Initialize custom cursor
  initCustomCursor();
  
  // Initialize scroll-triggered counter animation
  initCounters();
  
  // Initialize scroll progress indicator
  initScrollProgress();
}

/**
 * Initialize image carousel
 */
function initCarousel() {
  const carousel = document.querySelector('.carousel');
  if (!carousel) return;
  
  const track = carousel.querySelector('.carousel-track');
  const slides = carousel.querySelectorAll('.carousel-slide');
  const nextBtn = carousel.querySelector('.carousel-next');
  const prevBtn = carousel.querySelector('.carousel-prev');
  const dots = carousel.querySelector('.carousel-dots');
  
  if (!track || !slides.length) return;
  
  let currentIndex = 0;
  const slideWidth = slides[0].offsetWidth;
  
  // Create dot indicators
  if (dots) {
    slides.forEach((_, i) => {
      const dot = document.createElement('button');
      dot.classList.add('carousel-dot');
      if (i === 0) dot.classList.add('active');
      dot.addEventListener('click', () => goToSlide(i));
      dots.appendChild(dot);
    });
  }
  
  // Next button functionality
  if (nextBtn) {
    nextBtn.addEventListener('click', () => {
      currentIndex = (currentIndex + 1) % slides.length;
      updateCarousel();
    });
  }
  
  // Previous button functionality
  if (prevBtn) {
    prevBtn.addEventListener('click', () => {
      currentIndex = (currentIndex - 1 + slides.length) % slides.length;
      updateCarousel();
    });
  }
  
  // Touch swipe functionality
  let touchStartX = 0;
  let touchEndX = 0;
  
  carousel.addEventListener('touchstart', (e) => {
    touchStartX = e.changedTouches[0].screenX;
  });
  
  carousel.addEventListener('touchend', (e) => {
    touchEndX = e.changedTouches[0].screenX;
    handleSwipe();
  });
  
  function handleSwipe() {
    if (touchStartX - touchEndX > 50) {
      // Swipe left
      currentIndex = (currentIndex + 1) % slides.length;
      updateCarousel();
    } else if (touchEndX - touchStartX > 50) {
      // Swipe right
      currentIndex = (currentIndex - 1 + slides.length) % slides.length;
      updateCarousel();
    }
  }
  
  function goToSlide(index) {
    currentIndex = index;
    updateCarousel();
  }
  
  function updateCarousel() {
    track.style.transform = `translateX(-${currentIndex * slideWidth}px)`;
    
    // Update active dot
    if (dots) {
      const activeDot = dots.querySelector('.active');
      if (activeDot) activeDot.classList.remove('active');
      dots.children[currentIndex].classList.add('active');
    }
  }
  
  // Auto-advance carousel
  setInterval(() => {
    currentIndex = (currentIndex + 1) % slides.length;
    updateCarousel();
  }, 5000);
}

/**
 * Initialize tabs functionality
 */
function initTabs() {
  const tabsContainer = document.querySelector('.tabs-container');
  if (!tabsContainer) return;
  
  const tabs = tabsContainer.querySelectorAll('.tab');
  const tabContents = tabsContainer.querySelectorAll('.tab-content');
  
  tabs.forEach((tab, i) => {
    tab.addEventListener('click', () => {
      // Remove active class from all tabs and contents
      tabs.forEach(t => t.classList.remove('active'));
      tabContents.forEach(c => c.classList.remove('active'));
      
      // Add active class to clicked tab and corresponding content
      tab.classList.add('active');
      tabContents[i].classList.add('active');
    });
  });
}

/**
 * Initialize custom cursor effects
 */
function initCustomCursor() {
  const cursor = document.querySelector('.custom-cursor');
  if (!cursor) return;
  
  document.addEventListener('mousemove', (e) => {
    cursor.style.left = `${e.clientX}px`;
    cursor.style.top = `${e.clientY}px`;
  });
  
  document.addEventListener('mousedown', () => {
    cursor.classList.add('clicking');
  });
  
  document.addEventListener('mouseup', () => {
    cursor.classList.remove('clicking');
  });
  
  // Grow cursor on hoverable elements
  document.querySelectorAll('a, button, .hoverable').forEach(el => {
    el.addEventListener('mouseenter', () => {
      cursor.classList.add('grow');
    });
    
    el.addEventListener('mouseleave', () => {
      cursor.classList.remove('grow');
    });
  });
}

/**
 * Initialize counter animation
 */
function initCounters() {
  const counters = document.querySelectorAll('.counter');
  
  const counterObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const counter = entry.target;
          const target = parseInt(counter.dataset.target);
          const duration = parseInt(counter.dataset.duration) || 2000;
          let start = 0;
          const startTime = performance.now();
          
          const updateCounter = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            
            const value = Math.floor(progress * target);
            counter.textContent = value;
            
            if (progress < 1) {
              requestAnimationFrame(updateCounter);
            } else {
              counter.textContent = target;
            }
          };
          
          requestAnimationFrame(updateCounter);
          counterObserver.unobserve(counter);
        }
      });
    },
    { threshold: 0.5 }
  );
  
  counters.forEach(counter => {
    counterObserver.observe(counter);
  });
}

/**
 * Initialize scroll progress indicator
 */
function initScrollProgress() {
  const progressBar = document.querySelector('.scroll-progress');
  if (!progressBar) return;
  
  window.addEventListener('scroll', () => {
    const windowHeight = document.documentElement.scrollHeight - window.innerHeight;
    const scrolled = (window.scrollY / windowHeight) * 100;
    progressBar.style.width = `${scrolled}%`;
  });
}
