<?php

namespace App\Http\Middleware;

use App\UserRole;
use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

class EnsureUserHasRole
{
    /**
     * Handle an incoming request.
     *
     * @param  Closure(Request): (Response)  $next
     */
    public function handle(Request $request, Closure $next, string ...$roles): Response
    {
        $allowedRoles = array_values(array_filter(array_map(
            fn (string $role): ?UserRole => UserRole::tryFrom($role),
            $roles,
        )));

        abort_unless(
            $request->user()?->is_active && $request->user()->hasRole(...$allowedRoles),
            Response::HTTP_FORBIDDEN,
        );

        return $next($request);
    }
}
