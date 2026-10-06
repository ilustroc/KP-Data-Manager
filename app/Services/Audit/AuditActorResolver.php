<?php

namespace App\Services\Audit;

use App\Models\User;
use Illuminate\Database\Query\Builder;
use Illuminate\Support\Collection;
use Illuminate\Support\Str;

class AuditActorResolver
{
    /**
     * @param  iterable<int, object>  $records
     */
    public function attachDisplayNames(
        iterable $records,
        string $actorProperty = 'usuario',
        string $displayProperty = 'usuario_nombre',
    ): void {
        $records = collect($records);
        $displayNames = $this->resolveMany($records->pluck($actorProperty));

        foreach ($records as $record) {
            $actor = (string) ($record->{$actorProperty} ?? '');
            $record->{$displayProperty} = $displayNames[$actor] ?? $this->fallbackName($actor);
        }
    }

    /**
     * @param  iterable<int, mixed>  $actors
     * @return array<string, string>
     */
    public function resolveMany(iterable $actors): array
    {
        $actors = collect($actors)
            ->map(static fn (mixed $actor): string => trim((string) $actor))
            ->unique()
            ->values();

        $userIds = $this->userIdsFromActors($actors);
        $userNames = $userIds === []
            ? collect()
            : User::query()->whereKey($userIds)->pluck('name', 'id');

        return $actors->mapWithKeys(function (string $actor) use ($userNames): array {
            if (preg_match('/^user:(\d+)$/', $actor, $matches) === 1) {
                return [$actor => $userNames->get((int) $matches[1], 'Usuario no disponible')];
            }

            return [$actor => $this->fallbackName($actor)];
        })->all();
    }

    public function applyUserNameFilter(Builder $query, string $actorColumn, string $search): void
    {
        $actorKeys = User::query()
            ->where('name', 'like', '%'.trim($search).'%')
            ->pluck('id')
            ->map(static fn (int|string $id): string => 'user:'.$id)
            ->all();
        $includesSystem = $this->searchMatchesSystem($search);

        $query->where(function (Builder $query) use ($actorColumn, $actorKeys, $includesSystem): void {
            $query->whereIn($actorColumn, $actorKeys);

            if ($includesSystem) {
                $query->orWhere($actorColumn, 'like', 'cli:%');
            }
        });
    }

    /**
     * @param  Collection<int, string>  $actors
     * @return list<int>
     */
    private function userIdsFromActors(Collection $actors): array
    {
        return $actors
            ->map(static function (string $actor): ?int {
                return preg_match('/^user:(\d+)$/', $actor, $matches) === 1
                    ? (int) $matches[1]
                    : null;
            })
            ->filter(static fn (?int $id): bool => $id !== null)
            ->unique()
            ->values()
            ->all();
    }

    private function fallbackName(string $actor): string
    {
        if ($actor === '' || str_starts_with($actor, 'cli:')) {
            return 'Sistema';
        }

        return 'Usuario no disponible';
    }

    private function searchMatchesSystem(string $search): bool
    {
        $search = Str::lower(trim($search));

        return $search !== '' && str_contains(Str::lower('Sistema'), $search);
    }
}
