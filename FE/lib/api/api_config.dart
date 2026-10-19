abstract final class ApiConfig {
  static const baseUrl = String.fromEnvironment(
    'DAVEL_API_BASE_URL',
    defaultValue: 'http://127.0.0.1:8000',
  );
}
