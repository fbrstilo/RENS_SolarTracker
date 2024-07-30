const indicators = document.querySelectorAll('.line');

indicators.forEach(indicator => {
    let angle = parseFloat(indicator.parentElement.textContent);
    if (!isNaN(angle)) {
        // Rotate the line according to the angle
        indicator.style.transform = `rotate(${angle}deg)`;
      }
})