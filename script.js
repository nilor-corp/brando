const form = document.getElementById('interest-form');
const messageEl = document.getElementById('form-message');
const submitButton = document.getElementById('submit-button');
const emailInput = document.getElementById('email-input');

// Replace this URL with your new deployment URL from Google Apps Script
const GOOGLE_SCRIPT_URL = 'https://script.google.com/macros/s/AKfycbyYVUOfUJMpDhM58pCLNuukgrlava4MN4nhxPbg1d6OFQnIQ9mj4nPP7lozpiHmZgZkZg/exec';

form.addEventListener('submit', async e => {
    e.preventDefault();
    submitButton.disabled = true;
    submitButton.textContent = 'Submitting...';
    emailInput.disabled = true;
    messageEl.textContent = '';

    try {
        console.log('Submitting email:', emailInput.value);

        const formData = new URLSearchParams();
        formData.append('email', emailInput.value);

        await fetch(GOOGLE_SCRIPT_URL, {
            method: 'POST',
            mode: 'no-cors',
            body: formData
        });

        messageEl.textContent = "Thank you! We've received your interest.";
        messageEl.style.color = '#4ade80';
        form.reset();
    } catch (error) {
        console.error('Detailed error:', error);
        messageEl.textContent = `An error occurred. Please try again.`;
        messageEl.style.color = '#f87171';
    } finally {
        submitButton.disabled = false;
        submitButton.textContent = 'Register Interest';
        emailInput.disabled = false;
    }
});

// Smooth scroll for "to top" button
document.querySelector('.to-top-button').addEventListener('click', function(e) {
    e.preventDefault();
    window.scrollTo({
        top: 0,
        behavior: 'smooth'
    });
});

// Show/hide floating "to top" button based on scroll
const toTopButton = document.querySelector('.to-top-button');
const titleElement = document.querySelector('.gradient-text');
const scrollDownIndicator = document.querySelector('.scroll-down-indicator');

window.addEventListener('scroll', () => {
    const scrolled = window.scrollY > 200;
    const atTop = window.scrollY < 50;

    // Show "to top" button and shrink title
    toTopButton.classList.toggle('is-visible', scrolled);
    titleElement.classList.toggle('is-scrolled', scrolled);

    // Hide scroll-down indicator
    if (scrollDownIndicator) {
        scrollDownIndicator.classList.toggle('is-hidden', !atTop);
    }
});

