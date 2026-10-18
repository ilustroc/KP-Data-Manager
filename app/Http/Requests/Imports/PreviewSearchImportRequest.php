<?php

namespace App\Http\Requests\Imports;

use App\RefreshMode;
use Illuminate\Contracts\Validation\ValidationRule;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

class PreviewSearchImportRequest extends FormRequest
{
    /**
     * Determine if the user is authorized to make this request.
     */
    public function authorize(): bool
    {
        return $this->user()?->can('operate') ?? false;
    }

    /**
     * Get the validation rules that apply to the request.
     *
     * @return array<string, ValidationRule|array<mixed>|string>
     */
    public function rules(): array
    {
        $maximumKilobytes = max(1, (int) config('imports.max_web_upload_mb')) * 1024;
        $extensions = implode(',', config('imports.allowed_extensions'));

        return [
            'dataset_code' => ['required', Rule::in(config('imports.search.available_datasets', []))],
            'source_code' => ['required', 'string', 'max:64', 'regex:/\A[A-Z0-9][A-Z0-9_-]{0,63}\z/D'],
            'refresh_mode' => ['required', Rule::in([RefreshMode::FullReplace->value, RefreshMode::ScopeReplace->value])],
            'archivo' => ['required', 'file', "extensions:{$extensions}", "max:{$maximumKilobytes}"],
        ];
    }
}
