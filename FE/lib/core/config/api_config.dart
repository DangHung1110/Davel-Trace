abstract final class ApiConfig {
  static const baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://127.0.0.1:8000',
  );
  static const appMode = String.fromEnvironment(
    'APP_MODE',
    defaultValue: 'demo',
  );

  static bool get isDemo => appMode == 'demo' || appMode == 'test';
}
