// Add Member Photo preview
document.getElementById("photo").addEventListener("change", function (event) {
  const preview = document.getElementById("photo-preview");
  preview.innerHTML = ""; // Clear previous preview

  const file = event.target.files[0];
  if (file) {
    const reader = new FileReader();
    reader.onload = function (e) {
      const img = document.createElement("img");
      img.src = e.target.result;
      img.classList.add("w-full", "h-auto", "rounded-md");
      preview.appendChild(img);
    };
    reader.readAsDataURL(file);
  }
});
