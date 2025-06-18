document.addEventListener("DOMContentLoaded", function () {
  console.log("My JavaScript is loaded!"); // My JavaScript is loaded!

  // Removed slider functionality since it is no longer needed.

  // Initialize flatpickr for release date inputs if needed
  const releaseDateMinInput = document.getElementById("release-date-min");
  if (releaseDateMinInput) {
    flatpickr(releaseDateMinInput, {
      dateFormat: "Y-m-d",
      minDate: "2000-01-01",
      maxDate: "2024-12-31",
    });
  }

  const releaseDateMaxInput = document.getElementById("release-date-max");
  if (releaseDateMaxInput) {
    flatpickr(releaseDateMaxInput, {
      dateFormat: "Y-m-d",
      minDate: "2000-01-01",
      maxDate: "2024-12-31",
    });
  }

  // --- My JavaScript for the Login Page ---
  const togglePassword = document.getElementById("togglePassword");
  if (togglePassword) {
    // Checking if the element exists on the page
    togglePassword.addEventListener("click", function () {
      const passwordInput = document.getElementById("password");
      const type =
        passwordInput.getAttribute("type") === "password" ? "text" : "password";
      passwordInput.setAttribute("type", type);

      // Toggling the eye icon for my password field
      const icon = this.querySelector("i");
      icon.classList.toggle("fa-eye");
      icon.classList.toggle("fa-eye-slash");
    });
  }

  const loginForm = document.querySelector('form[action$="/login"]'); // Targeting my login form
  if (loginForm) {
    // Checking if the login form exists
    loginForm.addEventListener("submit", function (e) {
      const submitBtn = this.querySelector('button[type="submit"]');
      const originalText = submitBtn.innerHTML;

      submitBtn.innerHTML = '<span class="loading me-2"></span>Logging in...'; // Showing a loading spinner!
      submitBtn.disabled = true;

      // Re-enabling the button after a short delay, just in case the form submission is prevented by validation
      // (Flask will handle redirection on successful login)
      setTimeout(() => {
        submitBtn.innerHTML = originalText;
        submitBtn.disabled = false;
      }, 2000); // My chosen delay!
    });
  }

  // --- My JavaScript for the Register Page! ---
  const dobInput = document.getElementById("dob");
  if (dobInput) {
    // Checking if the DOB input exists on the page
    // Getting today's date in YYYY-MM-DD format for setting the max attribute dynamically
    const today = new Date();
    const year = today.getFullYear();
    const month = String(today.getMonth() + 1).padStart(2, "0"); // Month is 0-indexed, so I add 1
    const day = String(today.getDate()).padStart(2, "0");
    const todayDateFormatted = `${year}-${month}-${day}`;

    // Setting the max attribute for the dob input to today's date
    dobInput.setAttribute("max", todayDateFormatted);
  }
});
