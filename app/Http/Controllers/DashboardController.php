<?php

namespace App\Http\Controllers;

use App\Services\Dashboard\DashboardQueryService;
use Illuminate\Http\Request;
use Illuminate\Support\Str;
use Illuminate\View\View;

class DashboardController extends Controller
{
    public function index(Request $request, DashboardQueryService $dashboard): View
    {
        $hour = now(config('app.display_timezone'))->hour;
        $greeting = match (true) {
            $hour < 12 => 'Buenos días',
            $hour < 19 => 'Buenas tardes',
            default => 'Buenas noches',
        };

        return view('dashboard.index', [
            'firstName' => Str::of($request->user()->name)->trim()->before(' ')->toString(),
            'greeting' => $greeting,
            'recentImports' => $dashboard->recentImports(),
            'summary' => $dashboard->summary(),
        ]);
    }
}
