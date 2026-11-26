import 'dart:async';

import 'package:flutter/material.dart';

import '../../../core/errors/api_exception.dart';
import '../../../theme/app_theme.dart';
import '../../management/domain/models.dart';
import '../data/group_repository.dart';

String groupError(Object error) => switch (error) {
  ApiException(statusCode: 404) => 'Chuyến đi hoặc mục này không còn khả dụng.',
  ApiException(statusCode: 403) => 'Bạn không có quyền thực hiện thao tác này.',
  ApiException(statusCode: 422) => 'Kiểm tra lại thông tin rồi thử lại.',
  ApiException(:final message) => message,
  _ => 'Không thể kết nối. Hãy thử lại.',
};

String groupDate(String value) {
  final date = DateTime.tryParse(value);
  return date == null ? value : '${date.day}/${date.month}/${date.year}';
}

String groupDateRange(Json item) {
  final first = groupDate(textField(item, 'start_date'));
  final last = groupDate(textField(item, 'end_date'));
  return first == last || last.isEmpty ? first : '$first – $last';
}

String groupClock(String value) {
  final match = RegExp(r'(\d{2}:\d{2})').firstMatch(value);
  return match?.group(0) ?? value;
}

String groupRole(Json item) => switch (item['role']) {
  'leader' || 'owner' => 'Nhóm trưởng',
  'guest' => 'Khách đi cùng',
  _ => item['is_guest'] == true ? 'Khách đi cùng' : 'Thành viên',
};

class GroupState extends ChangeNotifier {
  GroupState(this.repository, this.tripId, [Json? initial]) : detail = initial;

  final GroupRepository repository;
  final String tripId;
  Json? detail;
  String? failure;
  bool _loading = false;
  bool _disposed = false;
  int _revision = 0;

  List<Json> get allMembers => jsonObjects(detail?['members']);
  List<Json> get members =>
      allMembers.where((person) => person['active'] != false).toList();
  String get memberId => detail?['member_id']?.toString() ?? '';
  bool get isLeader => const {'owner', 'leader'}.contains(detail?['role']);
  bool get canEdit => detail != null && detail?['read_only'] != true;

  String name(String id) =>
      allMembers
          .where((person) => person['id'] == id)
          .map((person) => textField(person, 'display_name'))
          .firstOrNull ??
      'Thành viên';

  Future<void> refresh() async {
    if (_loading || _disposed) return;
    _loading = true;
    final revision = _revision;
    try {
      final result = await repository.get(tripId);
      if (!_disposed && revision == _revision) {
        detail = result;
        failure = null;
      }
    } catch (error) {
      if (!_disposed && revision == _revision) {
        // If membership is revoked, remove previously shown private trip data.
        if (error is ApiException &&
            {401, 403, 404}.contains(error.statusCode)) {
          detail = null;
        }
        failure = groupError(error);
      }
    } finally {
      _loading = false;
      if (!_disposed && revision == _revision) notifyListeners();
    }
  }

  void update(Json response) {
    if (_disposed || response['trip_id'] == null) return;
    _revision++;
    detail = response;
    failure = null;
    notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }
}

class GroupPolling extends StatefulWidget {
  const GroupPolling({super.key, required this.onRefresh, required this.child});

  final Future<void> Function() onRefresh;
  final Widget child;

  @override
  State<GroupPolling> createState() => _GroupPollingState();
}

class _GroupPollingState extends State<GroupPolling>
    with WidgetsBindingObserver {
  Timer? _timer;
  bool _refreshing = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _start();
  }

  void _start() {
    if (_timer != null) return;
    _timer = Timer.periodic(const Duration(seconds: 5), (_) => _refresh());
  }

  Future<void> _refresh() async {
    if (!mounted || _refreshing || ModalRoute.of(context)?.isCurrent == false) {
      return;
    }
    _refreshing = true;
    try {
      await widget.onRefresh();
    } finally {
      _refreshing = false;
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      unawaited(_refresh());
      _start();
    } else {
      _timer?.cancel();
      _timer = null;
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => widget.child;
}

class GroupProblem extends StatelessWidget {
  const GroupProblem({super.key, required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) => Semantics(
    liveRegion: true,
    child: Material(
      color: Theme.of(context).colorScheme.errorContainer,
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 4),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(message),
            TextButton(onPressed: onRetry, child: const Text('Thử lại')),
          ],
        ),
      ),
    ),
  );
}

class GroupStatus extends StatelessWidget {
  const GroupStatus({super.key, required this.icon, required this.text});

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) => Row(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Icon(icon, color: AppColors.primary, size: 20),
      const SizedBox(width: 8),
      Expanded(child: Text(text, style: Theme.of(context).textTheme.bodySmall)),
    ],
  );
}

class GroupActions extends StatelessWidget {
  const GroupActions({super.key, required this.children});

  final List<Widget> children;

  @override
  Widget build(BuildContext context) => SafeArea(
    top: false,
    minimum: const EdgeInsets.fromLTRB(16, 8, 16, 12),
    child: Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: children,
    ),
  );
}

Future<bool> confirmGroupAction(
  BuildContext context, {
  required String title,
  required String description,
  required String action,
}) async =>
    await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        scrollable: true,
        title: Text(title),
        content: Text(description),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Quay lại'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: Text(action),
          ),
        ],
      ),
    ) ??
    false;

class GroupPlacePicker extends StatefulWidget {
  const GroupPlacePicker({
    super.key,
    required this.repository,
    this.title = 'Chọn địa điểm',
  });

  final GroupRepository repository;
  final String title;

  @override
  State<GroupPlacePicker> createState() => _GroupPlacePickerState();
}

class _GroupPlacePickerState extends State<GroupPlacePicker> {
  final _query = TextEditingController();
  Future<List<PoiItem>>? _result;

  void _search() {
    final query = _query.text.trim();
    if (query.isEmpty) return;
    FocusScope.of(context).unfocus();
    setState(() => _result = widget.repository.places(query));
  }

  @override
  void dispose() {
    _query.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text(widget.title)),
    body: SafeArea(
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: TextField(
              key: const Key('group-place-search'),
              controller: _query,
              maxLength: 120,
              autofocus: true,
              textInputAction: TextInputAction.search,
              onSubmitted: (_) => _search(),
              decoration: InputDecoration(
                labelText: 'Tên địa điểm',
                hintText: 'Ví dụ: Bảo tàng Chăm',
                counterText: '',
                suffixIcon: IconButton(
                  onPressed: _search,
                  tooltip: 'Tìm địa điểm',
                  icon: const Icon(Icons.search),
                ),
              ),
            ),
          ),
          Expanded(
            child: FutureBuilder<List<PoiItem>>(
              future: _result,
              builder: (context, snapshot) {
                if (_result == null) {
                  return const Padding(
                    padding: EdgeInsets.all(20),
                    child: Text('Tìm và chọn đúng địa điểm ở Đà Nẵng.'),
                  );
                }
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return const Center(child: CircularProgressIndicator());
                }
                if (snapshot.hasError) {
                  return Padding(
                    padding: const EdgeInsets.all(16),
                    child: GroupProblem(
                      message: 'Chưa tải được địa điểm.',
                      onRetry: _search,
                    ),
                  );
                }
                final places = snapshot.data ?? const [];
                if (places.isEmpty) {
                  return const Padding(
                    padding: EdgeInsets.all(20),
                    child: Text('Chưa tìm thấy. Hãy thử tên khác.'),
                  );
                }
                return ListView.separated(
                  keyboardDismissBehavior:
                      ScrollViewKeyboardDismissBehavior.onDrag,
                  itemCount: places.length,
                  separatorBuilder: (_, _) => const Divider(height: 1),
                  itemBuilder: (context, index) {
                    final place = places[index];
                    return ListTile(
                      key: ValueKey('group-place-${place.id}'),
                      contentPadding: const EdgeInsets.symmetric(
                        horizontal: 16,
                      ),
                      leading: const Icon(Icons.place_outlined),
                      title: Text(place.name),
                      onTap: () => Navigator.pop(context, place),
                    );
                  },
                );
              },
            ),
          ),
        ],
      ),
    ),
  );
}
