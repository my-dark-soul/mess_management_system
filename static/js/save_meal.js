document.getElementById("saveButton").addEventListener("click", function() {
    const mealData = [];

    // Loop through each member's meal inputs
    document.querySelectorAll(".border-t").forEach(memberRow => {
        const memberId = memberRow.querySelector(".meal-input").dataset.memberId;

        // Gather meal counts for each day
        const counts = Array.from(memberRow.querySelectorAll(".meal-input")).map(countInput => parseInt(countInput.value) || 0);

        mealData.push({ member_id: memberId, meal_counts: counts });
    });

    fetch("/save_meal_data/", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(mealData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert(data.message);
        } else {
            alert("Error: " + data.message);
        }
    })
    .catch(error => console.error("Error:", error));
});
