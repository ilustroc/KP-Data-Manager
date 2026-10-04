<?php

namespace App\Providers;

use App\Models\User;
use App\UserRole;
use Illuminate\Cache\RateLimiting\Limit;
use Illuminate\Database\Schema\Builder;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Gate;
use Illuminate\Support\Facades\RateLimiter;
use Illuminate\Support\ServiceProvider;
use Illuminate\Support\Str;

class AppServiceProvider extends ServiceProvider
{
    /**
     * Register any application services.
     */
    public function register(): void
    {
        //
    }

    /**
     * Bootstrap any application services.
     */
    public function boot(): void
    {
        Builder::defaultStringLength(191);

        Gate::define('administer', fn (User $user): bool => $user->is_active && $user->hasRole(UserRole::Admin));
        Gate::define('operate', fn (User $user): bool => $user->canOperate());
        Gate::define('view-data', fn (User $user): bool => $user->is_active);

        RateLimiter::for('login', function (Request $request): Limit {
            $email = Str::lower($request->string('email')->trim()->toString());

            return Limit::perMinute(5)->by(Str::transliterate($email.'|'.$request->ip()));
        });
    }
}
