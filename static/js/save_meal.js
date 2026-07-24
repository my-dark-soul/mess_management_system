document.getElementById("saveButton").addEventListener("click", function () {
  const mealData = [];

  document.querySelectorAll(".border-t").forEach((memberRow) => {
    // Get member ID from the row's first input
    const firstInput = memberRow.querySelector(".meal-input");

    // Skip rows where inputs don't exist (safety check)
    if (!firstInput) {
      console.warn("Skipping row — no meal-input found:", memberRow);
      return;
    }

    const memberId = firstInput.dataset.memberId;

    // Gather meal counts for each day as floats
    const counts = Array.from(memberRow.querySelectorAll(".meal-input")).map(
      (input) => parseFloat(input.value) || 0.0,
    );

    mealData.push({ member_id: memberId, meal_counts: counts });
  });

  // Don't send empty data
  if (mealData.length === 0) {
    alert("No meal data found to save.");
    return;
  }

  fetch("/save_meal_data/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(mealData),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        alert(data.message);
      } else {
        alert("Error: " + data.message);
      }
    })
    .catch((error) => {
      console.error("Error:", error);
      alert("Network error. Check your connection.");
    });
});
