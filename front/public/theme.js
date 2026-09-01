try {
  if (localStorage.getItem("cadence-theme") === "dark") {
    document.documentElement.classList.add("dark");
  }
} catch (error) {}
