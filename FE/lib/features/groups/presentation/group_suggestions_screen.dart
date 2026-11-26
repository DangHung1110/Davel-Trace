import 'package:flutter/material.dart';

import '../../management/domain/models.dart';
import '../data/group_repository.dart';
import 'group_shared.dart';
import 'group_suggestion_import.dart';

const _kinds = {
  'place': 'Điểm muốn ghé',
  'interest': 'Sở thích',
  'food': 'Ăn uống',
  'avoid': 'Điểm nên tránh',
  'accessibility': 'Hỗ trợ di chuyển',
  'profile': 'Sở thích từ hồ sơ',
};

class GroupSuggestionsScreen extends StatefulWidget {
  const GroupSuggestionsScreen({super.key, required this.group});
  final GroupState group;

  @override
  State<GroupSuggestionsScreen> createState() => _GroupSuggestionsScreenState();
}

class _GroupSuggestionsScreenState extends State<GroupSuggestionsScreen> {
  GroupState get group => widget.group;
  bool _busy = false;

  Future<void> _run(Future<Json> Function() request) async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      group.update(await request());
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(groupError(error))));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _add() async {
    final result = await Navigator.of(context).push<Json>(
      MaterialPageRoute(builder: (_) => _SuggestionEditor(group: group)),
    );
    if (result != null && mounted) group.update(result);
  }

  Future<void> _addByText() async {
    final result = await Navigator.of(context).push<Json>(
      MaterialPageRoute(builder: (_) => GroupSuggestionImport(group: group)),
    );
    if (result != null && mounted) group.update(result);
  }

  Future<void> _import() async {
    final confirmed = await confirmGroupAction(
      context,
      title: 'Dùng sở thích từ hồ sơ?',
      description: 'Sở thích phù hợp sẽ được thêm vào góp ý cho chuyến này và hiện với người trong nhóm.',
      action: 'Dùng sở thích',
    );
    if (!confirmed || !mounted) return;
    await _run(
      () => group.repository.post(group.tripId, '/suggestions', {
        'kind': 'interest',
        'title': 'Sở thích từ hồ sơ',
        'use_profile': true,
      }),
    );
  }

  Future<void> _remove(Json item) async {
    final confirmed = await confirmGroupAction(
      context,
      title: 'Xóa góp ý?',
      description:
          'Góp ý này sẽ không được tính khi nhóm trưởng lập lịch lần tới.',
      action: 'Xóa góp ý',
    );
    if (!confirmed || !mounted) return;
    await _run(
      () => group.repository.delete(group.tripId, '/suggestions/${item['id']}'),
    );
  }

  @override
  Widget build(BuildContext context) => GroupPolling(
    onRefresh: group.refresh,
    child: ListenableBuilder(
      listenable: group,
      builder: (context, _) {
        final suggestions = jsonObjects(group.detail?['suggestions']);
        return Scaffold(
          appBar: AppBar(
            title: const Text('Góp ý chuyến đi'),
            actions: [
              if (group.canEdit)
                PopupMenuButton<String>(
                  tooltip: 'Thêm cách góp ý',
                  enabled: !_busy,
                  onSelected: (value) =>
                      value == 'text' ? _addByText() : _import(),
                  itemBuilder: (_) => const [
                    PopupMenuItem(
                      value: 'text',
                      child: Text('Nhập bằng lời với AI'),
                    ),
                    PopupMenuItem(
                      value: 'profile',
                      child: Text('Dùng sở thích từ hồ sơ'),
                    ),
                  ],
                ),
            ],
          ),
          body: SafeArea(
            bottom: false,
            child: RefreshIndicator(
              onRefresh: group.refresh,
              child: ListView.builder(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.fromLTRB(20, 8, 20, 20),
                itemCount: suggestions.length + 1,
                itemBuilder: (context, index) {
                  if (index == 0) {
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          if (group.failure case final failure?)
                            GroupProblem(
                              message: failure,
                              onRetry: group.refresh,
                            ),
                          Text(
                            'Bạn muốn ghé đâu?',
                            style: Theme.of(context).textTheme.headlineSmall,
                          ),
                          const SizedBox(height: 6),
                          const Text(
                            'Chọn một điểm bạn muốn ghé nhất. Cả nhóm có thể ủng hộ đề xuất trước khi nhóm trưởng tạo lịch.',
                          ),
                          if (suggestions.isEmpty && group.detail != null) ...[
                            const SizedBox(height: 18),
                            const GroupStatus(
                              icon: Icons.place_outlined,
                              text: 'Chưa có góp ý. Bạn có thể gửi ý kiến đầu tiên.',
                            ),
                          ],
                        ],
                      ),
                    );
                  }
                  final item = suggestions[index - 1];
                  final member = textField(item, 'member_id');
                  final type = textField(item, 'kind');
                  final id = textField(item, 'id');
                  final enabled = item['approved'] == true;
                  final voted = item['voted'] == true;
                  final mayRemove =
                      group.canEdit &&
                      (member == group.memberId ||
                          (group.isLeader &&
                              group.members.any(
                                (person) =>
                                    person['id'] == member &&
                                    person['is_guest'] == true,
                              )));
                  final mayApprove =
                      group.canEdit &&
                      group.isLeader &&
                      const {'place', 'avoid', 'accessibility'}.contains(type);
                  return Column(
                    key: ValueKey('group-suggestion-$id'),
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Divider(height: 1),
                      const SizedBox(height: 10),
                      Row(
                        children: [
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  textField(item, 'title'),
                                  style: Theme.of(context)
                                      .textTheme
                                      .titleMedium,
                                ),
                                Text(
                                  '${_kinds[type] ?? 'Góp ý'} · ${group.name(member)}',
                                  style: Theme.of(context).textTheme.bodySmall,
                                ),
                              ],
                            ),
                          ),
                          if (mayRemove || mayApprove)
                            PopupMenuButton<String>(
                              tooltip: 'Tùy chọn góp ý',
                              enabled: !_busy,
                              onSelected: (action) async {
                                if (action == 'remove') {
                                  await _remove(item);
                                } else {
                                  await _run(
                                    () => group.repository.put(
                                      group.tripId,
                                      '/suggestions/$id/approval',
                                      {'enabled': !enabled},
                                    ),
                                  );
                                }
                              },
                              itemBuilder: (_) => [
                                if (mayApprove)
                                  PopupMenuItem(
                                    value: 'approve',
                                    child: Text(
                                      enabled
                                          ? 'Bỏ khỏi điều kiện chung'
                                          : 'Đưa vào điều kiện chung',
                                    ),
                                  ),
                                if (mayRemove)
                                  const PopupMenuItem(
                                    value: 'remove',
                                    child: Text('Xóa góp ý'),
                                  ),
                              ],
                            ),
                        ],
                      ),
                      if (textField(item, 'notes').isNotEmpty)
                        Padding(
                          padding: const EdgeInsets.only(top: 6),
                          child: Text(textField(item, 'notes')),
                        ),
                      if (type == 'place' &&
                          integerField(item, 'support_count') > 1)
                        Padding(
                          padding: const EdgeInsets.only(top: 6),
                          child: Text(
                            '${integerField(item, 'support_count')} người quan tâm đến điểm này',
                            style: Theme.of(context).textTheme.bodySmall,
                          ),
                        ),
                      Wrap(
                        spacing: 12,
                        runSpacing: 4,
                        crossAxisAlignment: WrapCrossAlignment.center,
                        children: [
                          if (enabled)
                            Text(
                              type == 'place'
                                  ? 'Điểm bắt buộc'
                                  : 'Điều kiện chung',
                              style: Theme.of(context).textTheme.labelLarge,
                            ),
                          if (item['priority'] == true)
                            Text(
                              'Ưu tiên của ${group.name(member)}',
                              style: Theme.of(context).textTheme.labelMedium,
                            ),
                          if (type == 'place')
                            TextButton.icon(
                              key: ValueKey('vote-suggestion-$id'),
                              onPressed: _busy || !group.canEdit
                                  ? null
                                  : () => _run(
                                      () => group.repository.put(
                                        group.tripId,
                                        '/suggestions/$id/vote',
                                        {'enabled': !voted},
                                      ),
                                    ),
                              icon: Icon(
                                voted
                                    ? Icons.thumb_up
                                    : Icons.thumb_up_outlined,
                                size: 18,
                              ),
                              label: Text(
                                voted
                                    ? 'Đã ủng hộ · ${integerField(item, 'votes')}'
                                    : 'Ủng hộ · ${integerField(item, 'votes')}',
                              ),
                            ),
                        ],
                      ),
                      const SizedBox(height: 8),
                    ],
                  );
                },
              ),
            ),
          ),
          bottomNavigationBar: !group.canEdit
              ? null
              : GroupActions(
                  children: [
                    FilledButton.icon(
                      key: const Key('add-group-suggestion'),
                      onPressed: _busy ? null : _add,
                      icon: const Icon(Icons.add),
                      label: const Text('Gửi góp ý'),
                    ),
                  ],
                ),
        );
      },
    ),
  );
}

class _SuggestionEditor extends StatefulWidget {
  const _SuggestionEditor({required this.group});
  final GroupState group;

  @override
  State<_SuggestionEditor> createState() => _SuggestionEditorState();
}

class _SuggestionEditorState extends State<_SuggestionEditor> {
  GroupState get group => widget.group;
  final _form = GlobalKey<FormState>();
  final _title = TextEditingController();
  final _notes = TextEditingController();
  late String _member = group.memberId;
  String _kind = 'place';
  bool _priority = true;
  bool _busy = false;
  PoiItem? _place;
  String? _error;
  bool get _catalogOnly => _kind == 'place' || _kind == 'avoid';

  Future<void> _pick() async {
    final place = await Navigator.of(context).push<PoiItem>(
      MaterialPageRoute(
        builder: (_) => GroupPlacePicker(repository: group.repository),
      ),
    );
    if (place != null && mounted) {
      setState(() {
        _place = place;
        _error = null;
      });
    }
  }

  Future<void> _submit() async {
    if (_busy || !(_form.currentState?.validate() ?? false)) return;
    if (_catalogOnly && _place == null) {
      setState(() => _error = 'Chọn địa điểm bạn muốn góp ý.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final response = await group.repository.post(
        group.tripId,
        '/suggestions',
        {
          'kind': _kind,
          'title': _catalogOnly ? _place!.name : _title.text.trim(),
          if (_catalogOnly) 'poi_id': _place!.id,
          if (_member != group.memberId) 'member_id': _member,
          if (_notes.text.trim().isNotEmpty) 'notes': _notes.text.trim(),
          'priority': _kind == 'place' && _priority,
        },
      );
      if (mounted) Navigator.pop(context, response);
    } catch (error) {
      if (mounted) {
        setState(() {
          _busy = false;
          _error = groupError(error);
        });
      }
    }
  }

  @override
  void dispose() {
    _title.dispose();
    _notes.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final guests = group.members.where((person) => person['is_guest'] == true);
    return Scaffold(
      appBar: AppBar(title: const Text('Gửi góp ý')),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Form(
            key: _form,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                if (group.isLeader && guests.isNotEmpty) ...[
                  DropdownButtonFormField<String>(
                    initialValue: _member,
                    isExpanded: true,
                    decoration: const InputDecoration(labelText: 'Góp ý cho'),
                    items: [
                      DropdownMenuItem(
                        value: group.memberId,
                        child: const Text('Tôi'),
                      ),
                      for (final guest in guests)
                        DropdownMenuItem(
                          value: textField(guest, 'id'),
                          child: Text(
                            textField(guest, 'display_name'),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                    ],
                    onChanged: _busy
                        ? null
                        : (value) {
                            if (value != null) setState(() => _member = value);
                          },
                  ),
                  const SizedBox(height: 16),
                ],
                DropdownButtonFormField<String>(
                  initialValue: _kind,
                  isExpanded: true,
                  decoration: const InputDecoration(labelText: 'Loại góp ý'),
                  items: [
                    for (final entry in _kinds.entries.where(
                      (entry) => entry.key != 'profile',
                    ))
                      DropdownMenuItem(
                        value: entry.key,
                        child: Text(entry.value),
                      ),
                  ],
                  onChanged: _busy
                      ? null
                      : (value) {
                          if (value != null) {
                            setState(() {
                              _kind = value;
                              _error = null;
                            });
                          }
                        },
                ),
                const SizedBox(height: 16),
                if (_catalogOnly)
                  OutlinedButton.icon(
                    onPressed: _busy ? null : _pick,
                    icon: const Icon(Icons.place_outlined),
                    label: Text(_place?.name ?? 'Tìm địa điểm'),
                  )
                else
                  TextFormField(
                    controller: _title,
                    maxLength: 120,
                    decoration: const InputDecoration(
                      labelText: 'Bạn muốn nhóm lưu ý điều gì?',
                    ),
                    validator: (value) => value == null || value.trim().isEmpty
                        ? 'Nhập nội dung góp ý.'
                        : null,
                    enabled: !_busy,
                  ),
                if (_kind == 'place')
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('Điểm muốn ghé nhất'),
                    subtitle: const Text(
                      'Chọn ưu tiên mới sẽ thay ưu tiên cũ.',
                    ),
                    value: _priority,
                    onChanged: _busy
                        ? null
                        : (value) => setState(() => _priority = value),
                  ),
                const SizedBox(height: 12),
                TextField(
                  controller: _notes,
                  maxLength: 400,
                  maxLines: 3,
                  enabled: !_busy,
                  decoration: const InputDecoration(
                    labelText: 'Ghi chú cho cả nhóm (tùy chọn)',
                  ),
                ),
                if (_error case final error?)
                  Text(
                    error,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                const SizedBox(height: 8),
                FilledButton(
                  key: const Key('submit-group-suggestion'),
                  onPressed: _busy ? null : _submit,
                  child: Text(_busy ? 'Đang gửi…' : 'Gửi góp ý'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
