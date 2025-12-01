## Description

<!-- Provide a brief description of the changes in this PR -->

## Type of Change

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Refactoring (no functional changes)
- [ ] Performance improvement
- [ ] Other (please describe):

## Testing

<!-- Describe the tests you ran and how to reproduce them -->

- [ ] Tested locally
- [ ] All existing tests pass
- [ ] Added new tests for new functionality

## Database Migration Checklist

<!-- If this PR includes a database migration, complete the following checklist -->

**Does this PR include a database migration?** [ ] Yes / [ ] No

If **Yes**, confirm:

- [ ] Synced with `main` branch immediately before running `flask db migrate`
- [ ] Migration file reviewed and verified correct `down_revision`
- [ ] Tested `flask db upgrade` successfully
- [ ] Tested `flask db downgrade` successfully
- [ ] Confirmed only ONE migration head exists (pre-push hook should verify this)
- [ ] Migration has a descriptive message/filename
- [ ] Breaking changes or data migrations documented in PR description

**Migration file location:**
<!-- e.g., migrations/versions/abc123_add_user_email.py -->

## Checklist

- [ ] My code follows the project's style guidelines
- [ ] I have performed a self-review of my own code
- [ ] I have commented my code where necessary, particularly in hard-to-understand areas
- [ ] I have updated the documentation accordingly
- [ ] My changes generate no new warnings or errors
- [ ] I have read and followed the [contributing guidelines](../CONTRIBUTING.md)

## Related Issues

<!-- Link any related issues here -->

Closes #

## Additional Notes

<!-- Any additional information that reviewers should know -->
