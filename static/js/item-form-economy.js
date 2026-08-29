document.addEventListener('DOMContentLoaded', function() {
  const economyDataEl = document.getElementById('economy-data');
  if (!economyDataEl || typeof EconomyBalanceChecker === 'undefined') {
    return;
  }

  const expectedWeeklyHours = parseFloat(economyDataEl.dataset.expectedWeeklyHours);
  const economyChecker = new EconomyBalanceChecker({
    warningsContainer: '#economy-warnings',
    expectedWeeklyHours: isNaN(expectedWeeklyHours) ? undefined : expectedWeeklyHours,
  });

  economyChecker
    .analyzeEconomy()
    .then((analysis) => {
      // NOTE: the rent CWI renderer produces a rent-specific "Pricing
      // Recommendation" card and has no lawful place on the Store surface. Store
      // pricing guidance is expressed exclusively through the tier recommendation
      // below (SPEC-ECON-003 §4.8 store tiers). Do NOT mount the rent panel here.
      const tierSelect = document.querySelector('[data-tier-select]');
      const tierRecommendation = document.getElementById('tier-recommendation');
      const tierRangeText = document.getElementById('tier-range-text');

      const tierRanges = analysis?.recommendations?.store_tiers;

      if (tierSelect && tierRecommendation && tierRangeText && tierRanges) {
        function updateTierRecommendation() {
          const selectedTier = tierSelect.value;
          const range = tierRanges[selectedTier];

          if (range && typeof range.min === 'number' && typeof range.max === 'number') {
            tierRangeText.textContent = `$${range.min.toFixed(2)} - $${range.max.toFixed(2)}`;
            tierRecommendation.style.display = 'block';
          } else {
            tierRecommendation.style.display = 'none';
          }
        }

        tierSelect.addEventListener('change', updateTierRecommendation);
        updateTierRecommendation();
      }
    })
    .catch(() => {
      console.log('Payroll not configured yet, skipping CWI display');
    });
});
