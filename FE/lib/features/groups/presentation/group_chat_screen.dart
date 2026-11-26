import 'dart:async';

import 'package:flutter/material.dart';

import '../../../core/errors/api_exception.dart';
import '../../management/domain/models.dart';
import '../../map/presentation/map_screen.dart';
import '../../map/presentation/map_stop.dart';
import '../data/group_repository.dart';
import 'group_shared.dart';

class GroupChatScreen extends StatefulWidget {
  const GroupChatScreen({super.key, required this.group, this.onOpenPlans});
  final GroupState group;
  final VoidCallback? onOpenPlans;

  @override
  State<GroupChatScreen> createState() => _GroupChatScreenState();
}

class _GroupChatScreenState extends State<GroupChatScreen> {
  GroupState get group => widget.group;
  final _draft = TextEditingController();
  final _draftFocus = FocusNode();
  final _scroll = ScrollController();
  final _messages = <String, Json>{};
  bool _loading = false;
  bool _sending = false;
  bool _initial = true;
  bool _more = false;
  String? _olderCursor;
  String? _failure;
  PoiItem? _place;
  Json? _replyingTo;

  @override
  void initState() {
    super.initState();
    unawaited(_refresh());
  }

  Future<void> _refresh({String? before}) async {
    if (_loading) return;
    _loading = true;
    try {
      final response = await group.repository.chat(
        group.tripId,
        before: before,
      );
      await group.refresh();
      if (!mounted) return;
      final rows = jsonObjects(response['items']);
      setState(() {
        for (final row in rows) {
          _messages[textField(row, 'id')] = row;
        }
        if (before != null || _olderCursor == null) {
          _more = response['has_more'] == true;
          if (rows.isNotEmpty) {
            _olderCursor = textField(_ordered(rows).last, 'id');
          }
        }
        _failure = null;
      });
    } catch (error) {
      if (mounted) {
        setState(() {
          if (error is ApiException &&
              {401, 403, 404}.contains(error.statusCode)) {
            _messages.clear();
            _more = false;
          }
          _failure = groupError(error);
        });
        unawaited(group.refresh());
      }
    } finally {
      _loading = false;
      if (mounted && _initial) setState(() => _initial = false);
    }
  }

  List<Json> _ordered(Iterable<Json> rows) {
    final ordered = rows.toList();
    ordered.sort((a, b) {
      final time = textField(
        b,
        'created_at',
      ).compareTo(textField(a, 'created_at'));
      return time == 0
          ? textField(b, 'id').compareTo(textField(a, 'id'))
          : time;
    });
    return ordered;
  }

  Future<void> _attach() async {
    final place = await Navigator.of(context).push<PoiItem>(
      MaterialPageRoute(
        builder: (_) => GroupPlacePicker(
          repository: group.repository,
          title: 'Chọn điểm hẹn',
        ),
      ),
    );
    if (mounted && place != null) setState(() => _place = place);
  }

  Future<void> _send() async {
    final draft = _draft.text.trim();
    final place = _place;
    if (_sending || (draft.isEmpty && place == null)) return;
    setState(() => _sending = true);
    try {
      final row = await group.repository.post(group.tripId, '/chat', {
        'text': draft.isEmpty ? 'Điểm hẹn' : draft,
        if (place != null) 'poi_id': place.id,
        if (_replyingTo case final reply?) 'reply_to_id': reply['id'],
      });
      if (!mounted) return;
      setState(() {
        _messages[textField(row, 'id')] = row;
        _place = null;
        _replyingTo = null;
        _failure = null;
      });
      _draft.clear();
      if (_scroll.hasClients) _scroll.jumpTo(0);
    } catch (error) {
      if (mounted) setState(() => _failure = groupError(error));
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  Future<void> _pin(Json? message) async {
    try {
      final result = await group.repository.put(
        group.tripId,
        '/chat/pinned-meeting',
        {'message_id': message?['id']},
      );
      if (!mounted) return;
      group.update({
        ...?group.detail,
        'pinned_meeting': result['pinned_meeting'],
      });
      setState(() => _failure = null);
    } catch (error) {
      if (mounted) setState(() => _failure = groupError(error));
    }
  }

  Future<void> _openPlace(Json message) async {
    try {
      final place = await group.repository.place(textField(message, 'poi_id'));
      if (!mounted) return;
      final color = Theme.of(context).colorScheme.primary;
      await Navigator.of(context).push<void>(
        MaterialPageRoute(
          builder: (context) => Scaffold(
            body: SafeArea(
              child: MapScreen(
                stops: [
                  MapStop(
                    id: place.id,
                    title: place.name,
                    subtitle: 'Điểm hẹn',
                    time: '',
                    durationMinutes: 0,
                    latitude: place.latitude,
                    longitude: place.longitude,
                    icon: Icons.flag_outlined,
                    color: color,
                  ),
                ],
                tripTitle: 'Điểm hẹn · ${place.name}',
                planRevision: 0,
                onOpenItinerary: () => Navigator.pop(context),
              ),
            ),
          ),
        ),
      );
    } catch (error) {
      if (mounted) setState(() => _failure = groupError(error));
    }
  }

  @override
  void dispose() {
    _draft.dispose();
    _draftFocus.dispose();
    _scroll.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final rows = _ordered(_messages.values);
    final readOnly = group.detail?['read_only'] == true || group.detail == null;
    final pinned = jsonObject(group.detail?['pinned_meeting']);
    return GroupPolling(
      onRefresh: _refresh,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Trò chuyện'),
          actions: [
            IconButton(
              tooltip: 'Tải lại tin nhắn',
              onPressed: _refresh,
              icon: const Icon(Icons.refresh),
            ),
          ],
        ),
        body: SafeArea(
          child: Column(
            children: [
              if (pinned.isNotEmpty)
                ListTile(
                  leading: const Icon(Icons.push_pin_outlined),
                  title: Text(textField(pinned, 'place_name')),
                  subtitle: const Text('Điểm hẹn của nhóm'),
                  onTap: () => _openPlace(pinned),
                  trailing: !readOnly && group.isLeader
                      ? IconButton(
                          tooltip: 'Bỏ ghim điểm hẹn',
                          onPressed: () => _pin(null),
                          icon: const Icon(Icons.close),
                        )
                      : null,
                ),
              if (_failure case String failure)
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: GroupProblem(message: failure, onRetry: _refresh),
                ),
              Expanded(
                child: _initial
                    ? const Center(child: CircularProgressIndicator())
                    : rows.isEmpty
                    ? const Center(
                        child: Padding(
                          padding: EdgeInsets.all(24),
                          child: Text(
                            'Chưa có tin nhắn. Dùng cuộc trò chuyện để thống nhất lịch hoặc gửi điểm hẹn.',
                            textAlign: TextAlign.center,
                          ),
                        ),
                      )
                    : ListView.builder(
                        controller: _scroll,
                        reverse: true,
                        padding: const EdgeInsets.symmetric(
                          horizontal: 16,
                          vertical: 10,
                        ),
                        itemCount: rows.length + (_more ? 1 : 0),
                        itemBuilder: (context, index) {
                          if (index == rows.length) {
                            return Center(
                              child: TextButton(
                                onPressed: () => _refresh(before: _olderCursor),
                                child: const Text('Xem tin nhắn cũ hơn'),
                              ),
                            );
                          }
                          final item = rows[index];
                          return _ChatMessage(
                            key: ValueKey('group-chat-${item['id']}'),
                            item: item,
                            isMine: item['member_id'] == group.memberId,
                            onOpenPlans: widget.onOpenPlans,
                            onReply: readOnly || item['kind'] == 'system'
                                ? null
                                : () {
                                    setState(() => _replyingTo = item);
                                    _draftFocus.requestFocus();
                                  },
                            onOpenPlace: item['poi_id'] == null
                                ? null
                                : () => _openPlace(item),
                            onPin:
                                !readOnly &&
                                    group.isLeader &&
                                    item['kind'] == 'meeting'
                                ? () => _pin(item)
                                : null,
                          );
                        },
                      ),
              ),
              if (!readOnly) ...[
                const Divider(height: 1),
                if (_replyingTo case final reply?)
                  ListTile(
                    dense: true,
                    leading: const Icon(Icons.reply_outlined),
                    title: Text(
                      textField(reply, 'text').isEmpty
                          ? textField(reply, 'place_name')
                          : textField(reply, 'text'),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    trailing: IconButton(
                      tooltip: 'Bỏ trả lời',
                      onPressed: _sending
                          ? null
                          : () => setState(() => _replyingTo = null),
                      icon: const Icon(Icons.close),
                    ),
                  ),
                if (_place case final place?)
                  ListTile(
                    dense: true,
                    leading: const Icon(Icons.location_on_outlined),
                    title: Text(place.name),
                    trailing: IconButton(
                      tooltip: 'Bỏ điểm hẹn',
                      onPressed: _sending
                          ? null
                          : () => setState(() => _place = null),
                      icon: const Icon(Icons.close),
                    ),
                  ),
                Padding(
                  padding: const EdgeInsets.fromLTRB(8, 8, 8, 10),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      IconButton(
                        key: const Key('attach-group-rendezvous'),
                        tooltip: 'Gửi điểm hẹn',
                        onPressed: _sending ? null : _attach,
                        icon: const Icon(Icons.add_location_alt_outlined),
                      ),
                      Expanded(
                        child: TextField(
                          key: const Key('group-chat-draft'),
                          controller: _draft,
                          focusNode: _draftFocus,
                          enabled: !_sending,
                          minLines: 1,
                          maxLines: 4,
                          maxLength: 800,
                          textCapitalization: TextCapitalization.sentences,
                          decoration: const InputDecoration(
                            hintText: 'Nhắn với cả nhóm',
                            counterText: '',
                          ),
                        ),
                      ),
                      const SizedBox(width: 4),
                      IconButton.filled(
                        key: const Key('send-group-message'),
                        tooltip: 'Gửi tin nhắn',
                        onPressed: _sending ? null : _send,
                        icon: const Icon(Icons.send_outlined),
                      ),
                    ],
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _ChatMessage extends StatelessWidget {
  const _ChatMessage({
    super.key,
    required this.item,
    required this.isMine,
    this.onReply,
    this.onOpenPlace,
    this.onPin,
    this.onOpenPlans,
  });

  final Json item;
  final bool isMine;
  final VoidCallback? onReply;
  final VoidCallback? onOpenPlace;
  final VoidCallback? onPin;
  final VoidCallback? onOpenPlans;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    final kind = textField(item, 'kind');
    final message = textField(item, 'text');
    if (kind == 'system' || kind == 'plans-ready' || kind == 'plan-published') {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 14),
        child: Column(
          children: [
            GroupStatus(icon: Icons.event_available_outlined, text: message),
            if (onOpenPlans != null)
              TextButton(
                onPressed: onOpenPlans,
                child: const Text('Xem lịch của nhóm'),
              ),
          ],
        ),
      );
    }
    final place = textField(item, 'place_name');
    final reply = jsonObject(item['reply']);
    final instant = DateTime.tryParse(textField(item, 'created_at'));
    final stamp = instant == null
        ? ''
        : groupClock(instant.toLocal().toIso8601String());
    return Align(
      alignment: isMine ? Alignment.centerRight : Alignment.centerLeft,
      child: FractionallySizedBox(
        widthFactor: .86,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 6),
          child: Column(
            crossAxisAlignment: isMine
                ? CrossAxisAlignment.end
                : CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 8),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(
                        '${isMine ? 'Bạn' : textField(item, 'display_name')}${stamp.isEmpty ? '' : ' · $stamp'}',
                        textAlign: isMine ? TextAlign.end : TextAlign.start,
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ),
                    if (onReply != null || onPin != null)
                      PopupMenuButton<String>(
                        tooltip: 'Tùy chọn tin nhắn',
                        onSelected: (value) =>
                            value == 'reply' ? onReply?.call() : onPin?.call(),
                        itemBuilder: (_) => [
                          if (onReply != null)
                            const PopupMenuItem(
                              value: 'reply',
                              child: Text('Trả lời'),
                            ),
                          if (onPin != null)
                            const PopupMenuItem(
                              value: 'pin',
                              child: Text('Ghim điểm hẹn'),
                            ),
                        ],
                      ),
                  ],
                ),
              ),
              const SizedBox(height: 4),
              DecoratedBox(
                decoration: BoxDecoration(
                  color: isMine
                      ? colors.primaryContainer
                      : colors.surfaceContainer,
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 10,
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      if (reply.isNotEmpty)
                        Padding(
                          padding: const EdgeInsets.only(bottom: 6),
                          child: Text(
                            'Trả lời · ${textField(reply, 'text')}',
                            style: Theme.of(context).textTheme.bodySmall,
                          ),
                        ),
                      if (message.isNotEmpty) Text(message),
                      if (place.isNotEmpty) ...[
                        if (message.isNotEmpty) const SizedBox(height: 6),
                        TextButton.icon(
                          onPressed: onOpenPlace,
                          icon: const Icon(Icons.place_outlined),
                          label: Text(place),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
