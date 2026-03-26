$env:STABLE_STEERING_GENERATION_BACKEND = "mock"
$env:STABLE_STEERING_ENFORCE_GPU_RUNTIME = "false"
$env:STABLE_STEERING_ALLOW_TEST_MOCK_BACKEND = "true"

npx playwright test --project=chrome --headed --workers=1
