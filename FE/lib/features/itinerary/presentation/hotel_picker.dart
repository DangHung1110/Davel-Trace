import 'package:flutter/material.dart';

import '../../management/data/management_repository.dart';
import '../../management/domain/models.dart';

class HotelPicker extends StatefulWidget {
  const HotelPicker({super.key, required this.repository});

  final ManagementRepository repository;

  @override
  State<HotelPicker> createState() => _HotelPickerState();
}

class _HotelPickerState extends State<HotelPicker> {
  final _query = TextEditingController();
  late Future<List<PoiItem>> _results;

  Future<List<PoiItem>> _findHotels() =>
      widget.repository.searchPois(_query.text.trim(), category: 'lodging');

  @override
  void initState() {
    super.initState();
    _results = _findHotels();
  }

  void _search() {
    FocusScope.of(context).unfocus();
    final results = _findHotels();
    setState(() {
      _results = results;
    });
  }

  @override
  void dispose() {
    _query.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Padding(
    padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
    child: FractionallySizedBox(
      heightFactor: .78,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Chọn nơi lưu trú',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 12),
            TextField(
              key: const Key('hotel-search-field'),
              controller: _query,
              maxLength: 120,
              textInputAction: TextInputAction.search,
              onSubmitted: (_) => _search(),
              decoration: InputDecoration(
                hintText: 'Tìm theo tên khách sạn',
                counterText: '',
                suffixIcon: IconButton(
                  key: const Key('hotel-search-button'),
                  tooltip: 'Tìm nơi lưu trú',
                  onPressed: _search,
                  icon: const Icon(Icons.search),
                ),
              ),
            ),
            const SizedBox(height: 8),
            Expanded(
              child: FutureBuilder<List<PoiItem>>(
                future: _results,
                builder: (context, snapshot) {
                  if (snapshot.connectionState != ConnectionState.done) {
                    return const Center(child: CircularProgressIndicator());
                  }
                  if (snapshot.hasError) {
                    return ListView(
                      children: [
                        const Text('Không tải được danh sách nơi lưu trú.'),
                        TextButton(
                          onPressed: _search,
                          child: const Text('Thử lại'),
                        ),
                      ],
                    );
                  }
                  final hotels = snapshot.data ?? const [];
                  if (hotels.isEmpty) {
                    return const Text('Không tìm thấy nơi lưu trú phù hợp.');
                  }
                  return ListView.builder(
                    itemCount: hotels.length,
                    itemBuilder: (context, index) {
                      final hotel = hotels[index];
                      return ListTile(
                        key: ValueKey('hotel-result-${hotel.id}'),
                        leading: const Icon(Icons.hotel_outlined),
                        title: Text(hotel.name),
                        onTap: () => Navigator.pop(context, hotel),
                      );
                    },
                  );
                },
              ),
            ),
          ],
        ),
      ),
    ),
  );
}
