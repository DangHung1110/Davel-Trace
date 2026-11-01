import 'dart:math';

abstract final class CorrelationId {
  static final Random _random = Random.secure();

  static String create() {
    final time = DateTime.now().microsecondsSinceEpoch.toRadixString(16);
    final random = List.generate(
      3,
      (_) => _random.nextInt(0x7fffffff).toRadixString(16).padLeft(8, '0'),
    ).join();
    return 'mobile-$time-$random';
  }
}
