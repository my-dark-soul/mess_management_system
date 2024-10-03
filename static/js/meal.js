  // Function to calculate total meals for each row
  function calculateTotalMeals() {
    // Get all table rows
    const rows = document.querySelectorAll("#meal-table tbody tr");

    rows.forEach(row => {
      // Get all meal inputs for this row
      const meals = row.querySelectorAll(".meal-input");

      // Calculate total meals
      let total = 0;
      meals.forEach(meal => {
        total += parseFloat(meal.value) || 0;  // Safely parse the meal value
      });

      // Update the total meal cell
      row.querySelector(".total-meal").textContent = total;
    });
  }

  // Event listener to recalculate total when any meal value changes
  document.querySelectorAll(".meal-input").forEach(input => {
    input.addEventListener("input", calculateTotalMeals);
  });

  // Call the function initially to set total meals
  calculateTotalMeals();