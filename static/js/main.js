document.addEventListener("DOMContentLoaded", function () {
  console.log("My JavaScript is loaded!"); // My JavaScript is loaded!

  // Initialize flatpickr for release date inputs if needed
  // This part is for any date pickers, if I ever add them!
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
      // Changing the input type between password and text
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
      }, 3000); // My chosen delay!
    });
  }

  // --- My JavaScript for the Register Page ---
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

  // --- My JavaScript for confirming game removal from the list! ---
  // Adding event listeners to all "Remove" buttons on the "My Games" page
  document.querySelectorAll(".confirm-remove-game").forEach((button) => {
    button.addEventListener("click", function (event) {
      // This will prevent the form from submitting right away
      event.preventDefault();
      // Using a custom confirmation message instead of `window.confirm`
      showCustomConfirm(
        "Are you sure you want to remove this game from your list?",
        () => {
          // If the user confirms, then I'll submit the form
          this.closest("form").submit();
        }
      );
    });
  });

  // --- Custom Confirmation Modal Logic ---
  // A simple function to create and show a custom confirmation dialog
  function showCustomConfirm(message, callback) {
    // Create the modal HTML elements
    const modalHtml = `
      <div class="modal fade" id="customConfirmModal" tabindex="-1" aria-labelledby="customConfirmModalLabel" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content">
            <div class="modal-header bg-primary text-white">
              <h5 class="modal-title" id="customConfirmModalLabel">Confirm Action</h5>
              <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
              ${message}
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
              <button type="button" class="btn btn-danger" id="confirmActionButton">Confirm</button>
            </div>
          </div>
        </div>
      </div>
    `;

    // Add the modal HTML to the body
    document.body.insertAdjacentHTML("beforeend", modalHtml);

    // Get the modal element and create a Bootstrap modal instance
    const customConfirmModal = new bootstrap.Modal(
      document.getElementById("customConfirmModal")
    );

    // Set up the click handler for the confirm button
    const confirmButton = document.getElementById("confirmActionButton");
    confirmButton.onclick = () => {
      // Execute the callback function if confirmed
      callback();
      // Close the modal after action
      customConfirmModal.hide();
      // Remove the modal from the DOM after it's hidden to keep things clean
      customConfirmModal._element.addEventListener(
        "hidden.bs.modal",
        function () {
          customConfirmModal._element.remove();
        }
      );
    };

    // Show the modal
    customConfirmModal.show();
  }
});
