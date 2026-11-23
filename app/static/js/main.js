/**
 * FraudGuard AI - Enterprise Frontend Client Script
 */

document.addEventListener('DOMContentLoaded', function () {
  // 1. Auto-dismiss flash alerts
  const flashAlerts = document.querySelectorAll('.alert-dismissible');
  flashAlerts.forEach(alert => {
    setTimeout(() => {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
      if (bsAlert) bsAlert.close();
    }, 6000);
  });

  // 2. Initialize Bootstrap Tooltips
  const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl);
  });

  // 3. Analysis Form Scenario Presets
  const scenarioNormalBtn = document.getElementById('btn-preset-normal');
  const scenarioDrainBtn = document.getElementById('btn-preset-drain');
  const scenarioVelocityBtn = document.getElementById('btn-preset-velocity');
  const scenarioNewAccountBtn = document.getElementById('btn-preset-newacc');

  function setFormField(id, value) {
    const el = document.getElementById(id);
    if (el) {
      el.value = value;
      el.dispatchEvent(new Event('change'));
    }
  }

  if (scenarioNormalBtn) {
    scenarioNormalBtn.addEventListener('click', function () {
      setFormField('amount', '65.00');
      setFormField('transaction_type', 'Payment');
      setFormField('sender_account', 'ACC-SAFE-88210');
      setFormField('receiver_account', 'MERCHANT-99120');
      setFormField('channel', 'Mobile Banking');
      setFormField('location', 'Domestic');
      setFormField('device', 'Mobile App (Recognized)');
      setFormField('frequency_24h', '2');
      setFormField('account_age_days', '520');
      setFormField('previous_amount', '55.00');
    });
  }

  if (scenarioDrainBtn) {
    scenarioDrainBtn.addEventListener('click', function () {
      setFormField('amount', '42500.00');
      setFormField('transaction_type', 'Transfer');
      setFormField('sender_account', 'ACC-TARGET-10293');
      setFormField('receiver_account', 'ACC-MULE-44910');
      setFormField('channel', 'Internet Banking');
      setFormField('location', 'Cross-Border (Unusual)');
      setFormField('device', 'New / Unrecognized Device');
      setFormField('frequency_24h', '12');
      setFormField('account_age_days', '180');
      setFormField('previous_amount', '120.00');
    });
  }

  if (scenarioVelocityBtn) {
    scenarioVelocityBtn.addEventListener('click', function () {
      setFormField('amount', '950.00');
      setFormField('transaction_type', 'Transfer');
      setFormField('sender_account', 'ACC-CARD-39481');
      setFormField('receiver_account', 'ACC-DEST-99321');
      setFormField('channel', 'UPI');
      setFormField('location', 'High-Risk Domestic');
      setFormField('device', 'New / Unrecognized Device');
      setFormField('frequency_24h', '32');
      setFormField('account_age_days', '90');
      setFormField('previous_amount', '80.00');
    });
  }

  if (scenarioNewAccountBtn) {
    scenarioNewAccountBtn.addEventListener('click', function () {
      setFormField('amount', '16800.00');
      setFormField('transaction_type', 'Transfer');
      setFormField('sender_account', 'ACC-NEW-00192');
      setFormField('receiver_account', 'ACC-OFFSHORE-774');
      setFormField('channel', 'Internet Banking');
      setFormField('location', 'Cross-Border (Unusual)');
      setFormField('device', 'New / Unrecognized Device');
      setFormField('frequency_24h', '2');
      setFormField('account_age_days', '6');
      setFormField('previous_amount', '20.00');
    });
  }

  // 4. Loading state for Analysis Form Submission
  const analyzeForm = document.getElementById('transaction-analysis-form');
  const analyzeSubmitBtn = document.getElementById('submit-analysis-btn');

  if (analyzeForm && analyzeSubmitBtn) {
    analyzeForm.addEventListener('submit', function () {
      analyzeSubmitBtn.disabled = true;
      analyzeSubmitBtn.innerHTML = `
        <span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
        Evaluating ML Models...
      `;
    });
  }

  // 5. Copy Transaction ID
  document.querySelectorAll('.btn-copy-ref').forEach(btn => {
    btn.addEventListener('click', function () {
      const ref = this.getAttribute('data-ref');
      if (ref) {
        navigator.clipboard.writeText(ref).then(() => {
          const originalTitle = this.innerHTML;
          this.innerHTML = '<i class="bi bi-check2 text-success"></i> Copied';
          setTimeout(() => { this.innerHTML = originalTitle; }, 2000);
        });
      }
    });
  });
});
